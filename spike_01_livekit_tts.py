#!/usr/bin/env python3
"""
Spike 01: Validate that LiveKit can feed external text (AsyncIterable[str]) into TTS
without being an LLM provider itself.

Core question: Can LiveKit act as a passive pipe for external SSE text → TTS?
Or does it require its own LLM provider between STT and TTS?
"""

import asyncio
import logging
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.agents.llm import ChatContext
from livekit.agents.voice import AgentSession as VoiceAgentSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PassthroughAgent(Agent):
    """Minimal agent that pipes external text to TTS.
    
    Goal: Validate that we can feed arbitrary text into LiveKit's TTS pipeline
    without LiveKit requiring its own LLM provider.
    """
    
    def __init__(self):
        super().__init__(
            instructions="You are a passthrough. You do nothing. Just pipe text to TTS.",
        )
        self._test_text_iterator = None
    
    async def on_enter(self):
        """Called when agent joins the room."""
        logger.info("Agent entered room")
        
        # Test: Can we just yield arbitrary text to TTS?
        # This simulates what the intermediary would do with Hermes SSE deltas
        
        test_texts = [
            "First, let me check the Docker logs.",
            "I can see a permission denied error on the Docker socket.",
            "Run this command to fix it.",
        ]
        
        async def text_stream():
            for text in test_texts:
                logger.info(f"Yielding text to TTS: {text!r}")
                yield text
                await asyncio.sleep(0.5)  # Simulate delay between sentences
        
        # Try 1: Use session.say() with an AsyncIterable[str]
        try:
            logger.info("ATTEMPT: session.say(AsyncIterable[str])")
            await self.session.say(text_stream())
            logger.info("SUCCESS: session.say() accepted external text stream")
        except Exception as e:
            logger.error(f"FAIL: session.say() rejected external text: {e}")
        
        # Try 2: Use session.say() with a single string   
        try:
            logger.info("ATTEMPT: session.say(single_string)")
            await self.session.say("This is a direct test of the TTS pipeline.")
            logger.info("SUCCESS: session.say() accepted single string")
        except Exception as e:
            logger.error(f"FAIL: session.say() rejected single string: {e}")


async def entrypoint(ctx: JobContext):
    """Job entry point."""
    logger.info("Starting spike test")
    
    agent = PassthroughAgent()
    
    session = AgentSession()
    
    await session.start(agent=agent, room=ctx.room)
    
    # Keep alive for observation
    await asyncio.sleep(30)
    
    logger.info("Spike test complete")


if __name__ == "__main__":
    # This is a basic structure; actual execution requires a LiveKit room connection
    # For now, just verify imports and structure
    logger.info(f"LiveKit Agent class: {Agent}")
    logger.info(f"LiveKit AgentSession class: {AgentSession}")
    print("Import check passed. Full test requires running LiveKit server + room.")
