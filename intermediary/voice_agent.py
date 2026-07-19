"""Voice Agent — LiveKit VoicePipelineAgent wrapper.

The VoicePipelineAgent handles:
- STT (speech-to-text) via Deepgram
- LLM (the intermediary) via OpenAI-compatible
- TTS (text-to-speech) via Cartesia
- VAD (voice activity detection)
- Turn-taking and barge-in

The intermediary system prompt encodes refine/distill/steer behaviors.
When the LLM calls query_hermes, the tool returns the distilled response.
"""

import asyncio
import logging
from typing import Optional

from livekit.agents import AgentSession, function_tool, llm
from livekit.plugins import openai, deepgram, cartesia

from .hermes_client import HermesClient
from .distillation import DistillationBuffer, distill
from .config import IntermediaryConfig

logger = logging.getLogger(__name__)

INTERMEDIARY_SYSTEM_PROMPT = """You are the intermediary between the user and Hermes (a powerful AI agent).

Your behaviors:
1. REFINE: When the user speaks in fragments or with vague references, clarify their intent 
   using conversation context before sending to Hermes.
2. DISTILL: When Hermes responds with long technical output, summarize it naturally 
   for speech (1-2 sentences).
3. STEER: When the user interrupts, capture their correction and inject it.

Rules:
- Preserve user intent exactly — never change what they are asking for
- Resolve pronouns like "that", "it", "the thing" using conversation history
- Keep distilled output to 1-2 natural sentences
- If the user interrupts, stop speaking immediately and listen
- After refining, call query_hermes with the refined prompt
- You do NOT do heavy reasoning — that is Hermes's job

Conversation context:
{intent_history}
"""


class VoiceIntermediaryAgent:
    """LiveKit VoicePipelineAgent wrapper for the intermediary."""
    
    def __init__(self, config: IntermediaryConfig = None):
        self.config = config or IntermediaryConfig()
        self.hermes = HermesClient(self.config.hermes.url)
        self.session: Optional[AgentSession] = None
    
    def _get_tools(self):
        """Get function tools for the intermediary LLM."""
        hermes = self.hermes
        
        @function_tool
        async def query_hermes(prompt: str) -> str:
            """Query Hermes and return the distilled response for speech.
            
            Args:
                prompt: The refined prompt to send to Hermes.
            
            Returns:
                The distilled, speech-friendly response.
            """
            try:
                stream_id = await hermes.start_chat(prompt, "default")
                
                buffer = DistillationBuffer()
                distilled_parts = []
                
                async for delta in hermes.stream_chat(stream_id):
                    sentence = buffer.feed(delta)
                    if sentence:
                        distilled = await distill(sentence)
                        if distilled:
                            distilled_parts.append(distilled)
                
                # Flush remaining
                final = buffer.flush()
                if final:
                    d = await distill(final)
                    if d:
                        distilled_parts.append(d)
                
                return " ".join(distilled_parts) if distilled_parts else "Hermes didn't respond."
            
            except Exception as e:
                logger.error(f"query_hermes error: {e}")
                return f"Error contacting Hermes: {e}"
        
        return [query_hermes]


async def entrypoint(room: str = "intermediary-room", token: str = None):
    """Start the voice agent.
    
    Args:
        room: LiveKit room name to join
        token: LiveKit access token
    """
    import os
    
    config = IntermediaryConfig()
    agent = VoiceIntermediaryAgent(config)
    
    # Create LiveKit session
    session = AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o-mini", api_key=os.environ.get("OPENAI_API_KEY")),
        tts=cartesia.TTS(api_key=os.environ.get("CARTESIA_API_KEY")),
    )
    
    agent.session = session
    
    # Set system prompt
    session.llm.instructions = INTERMEDIARY_SYSTEM_PROMPT
    
    # Add tools
    tools = agent._get_tools()
    session.llm.tools.extend(tools)
    
    # Connect to room
    # Note: Requires LiveKit server running and valid token
    logger.info(f"Connecting to room: {room}")
    
    # Start session
    await session.start(room=room, token=token)
    
    # Keep alive
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(entrypoint())
