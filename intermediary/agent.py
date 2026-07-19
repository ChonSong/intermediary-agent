"""Intermediary Agent — LiveKit Agent subclass.

The intermediary is a thin LLM-powered agent that:
1. Refines messy user input into structured prompts
2. Distills Hermes' verbose output into natural speech
3. Handles barge-in steering (user-initiated, non-interrupting)

Hermes runs as a separate API (NOT a LiveKit function call).
"""

import logging
from typing import AsyncIterable, Optional

from livekit.agents import Agent, AgentSession, JobContext
from livekit.agents.voice import AgentSession as VoiceAgentSession

from .hermes_client import HermesClient
from .distillation import DistillationBuffer, distill
from .steering import BargeInStateMachine
from .session import SessionManager

logger = logging.getLogger(__name__)


# System prompt encodes all three behaviors
INTERMEDIARY_SYSTEM_PROMPT = """You are a thin intermediary between the user and Hermes (a powerful AI agent).

Your job:
1. REFINE: When the user speaks in fragments or with vague references, clarify their 
   intent using conversation context before sending to Hermes.
2. DISTILL: When Hermes responds with long technical output, summarize it naturally 
   for speech.
3. STEER: When the user interrupts (barge-in), capture their correction and inject 
   it into the next exchange.

Rules:
- Preserve user intent exactly — never change what they're asking for
- Resolve pronouns using conversation history
- Keep distilled output to 1-2 sentences for natural speech
- If the user interrupts, stop speaking immediately and listen
- You do NOT do heavy reasoning — that's Hermes's job.

Previous topics: {intent_history}
Current focus: {current_topic}
"""


class IntermediaryAgent(Agent):
    """
    LiveKit Agent that acts as the intermediary between user and Hermes.
    
    Architecture:
    - LiveKit handles WebRTC audio + transcription events (the "watch everything" UI)
    - HermesClient handles HTTP/SSE to Hermes API (the "brain")
    - IntermediaryAgent translates between them (ears + mouth)
    """
    
    def __init__(self, hermes_client: HermesClient, session_manager: SessionManager):
        super().__init__(
            instructions=INTERMEDIARY_SYSTEM_PROMPT,
        )
        self.hermes = hermes_client
        self.sessions = session_manager
        self._current_session_id: Optional[str] = None
        self._barge_in_sm = BargeInStateMachine()
        self._distill_buffer = DistillationBuffer()
    
    async def on_enter(self):
        """Called when agent joins the room."""
        logger.info("Intermediary agent entered room")
    
    async def on_user_speech_committed(self, text: str):
        """
        Called when STT commits user text (from LiveKit).
        
        Handles both:
        - Normal turn (LISTENING → SPEAKING)
        - Barge-in (SPEAKING → STALE → immediate steer injection)
        """
        logger.info(f"User speech committed: {text}")
        
        if self._barge_in_sm.steer_active:
            # We're in barge-in mode; this is the steer text
            self._barge_in_sm.on_user_speech(text)
            # Immediately inject steer while Hermes is running
            await self._inject_steer(text)
            return
        
        if self._barge_in_sm.state == BargeInStateMachine.SPEAKING:
            # Normal barge-in during agent speech
            self._barge_in_sm.on_user_speech(text)
            # Immediately inject steer
            await self._inject_steer(text)
            return
        
        # Normal turn: refine → send to Hermes → distill → TTS
        refined = self._refine(text)
        logger.info(f"Refined: {text!r} → {refined!r}")
        
        # Start Hermes run
        stream_id = await self.hermes.start_chat(refined, self._current_session_id)
        
        # Pipe Hermes SSE → distillation → LiveKit TTS
        await self.session.say(
            self._hermes_stream_to_livekit(stream_id)
        )
    
    async def _hermes_stream_to_livekit(self, stream_id: str) -> AsyncIterable[str]:
        """
        Translate Hermes SSE stream into LiveKit's expected input format.
        
        Handles:
        - Buffering SSE deltas to sentence boundaries
        - Dropping stale deltas after barge-in
        - Distillation per sentence
        """
        self._distill_buffer = DistillationBuffer()
        
        async for delta in self.hermes.stream_chat(stream_id):
            # Drop deltas if steer is pending
            if self._barge_in_sm.should_drop_delta():
                logger.debug(f"Dropping stale delta: {delta!r}")
                continue
            
            # Buffer delta and check for sentence boundary
            sentence = self._distill_buffer.feed(delta)
            if sentence:
                distilled = await distill(sentence)
                if distilled:
                    yield distilled
        
        # Flush remaining buffer
        final = self._distill_buffer.flush()
        if final:
            distilled = await distill(final)
            if distilled:
                yield distilled
        
        # Hermes finished — transition state
        self._barge_in_sm.on_hermes_finish()
    
    def _refine(self, text: str) -> str:
        """Refine messy input. Phase 1: placeholder. Phase 1.3+: LLM call."""
        # Simple filler removal for now
        import re
        refined = re.sub(r'^(um+|so+|like+|you know+)\s*', '', text, flags=re.IGNORECASE)
        return refined.strip() or text.strip()
    
    async def _inject_steer(self, text: str):
        """Inject steer into Hermes (non-interrupting)."""
        if self._current_session_id:
            try:
                result = await self.hermes.steer(self._current_session_id, text)
                logger.info(f"Steer result: {result}")
            except Exception as e:
                logger.error(f"Steer injection failed: {e}")


async def entrypoint(ctx: JobContext):
    """Job entry point — called by LiveKit CLI."""
    from .config import IntermediaryConfig
    
    config = IntermediaryConfig()
    
    hermes_client = HermesClient(
        base_url=config.hermes.url,
        api_key=config.hermes.api_key,
    )
    
    session_manager = SessionManager()
    
    agent = IntermediaryAgent(
        hermes_client=hermes_client,
        session_manager=session_manager,
    )
    
    session = AgentSession(
        # STT/TTS providers configured via LiveKit worker
    )
    
    await session.start(agent=agent, room=ctx.room)
