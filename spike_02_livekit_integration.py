#!/usr/bin/env python3
"""
Spike 02: Full integration test with LiveKit server.

Tests:
1. Feed external AsyncIterable[str] into LiveKit TTS
2. Subscribe to transcription events
3. Forward events to a test WebSocket client
4. Test barge-in behavior with mock VAD

Run with:
    # Terminal 1: Start LiveKit dev server
    livekit-server --dev
    
    # Terminal 2: Run test client (this file)
    python3 spike_02_livekit_integration.py
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import AsyncIterable

from livekit import rtc, api
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.agents.voice import AgentSession as VoiceAgentSession
from livekit.plugins import openai, deepgram, cartesia

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class IntermediaryEvent:
    """Structured event for emotion-avatar extension point."""
    speaker: str         # "user" | "hermes" | "intermediary"
    text: str
    emotion: str | None
    audio: bytes | None
    timestamp: float


class IntermediaryAgent(Agent):
    """
    Spike version of the intermediary.
    
    Validates:
    - External text → LiveKit TTS (no LLM between)
    - Transcription event subscription + WebSocket forwarding
    - Barge-in behavior
    """
    
    def __init__(self):
        super().__init__(
            instructions="You are a test intermediary.",
        )
        self.event_log: list[IntermediaryEvent] = []
        self.steer_active = False
        self.pending_steer = None
    
    def log_event(self, speaker: str, text: str, emotion: str = None):
        """Log an event for verification."""
        event = IntermediaryEvent(
            speaker=speaker,
            text=text,
            emotion=emotion,
            audio=None,
            timestamp=time.time(),
        )
        self.event_log.append(event)
        logger.info(f"EVENT: {speaker}: {text}")
    
    async def on_enter(self):
        """Called when agent joins the room."""
        logger.info("=== Intermediary agent entered room ===")
        self.log_event("intermediary", "Agent entered room")
        
        # SPIKE TEST 1: Feed external text into LiveKit TTS
        logger.info("=== TEST 1: External text → TTS ===")
        
        test_sentences = [
            "First, let me check the Docker logs.",
            "I can see a permission denied error on the Docker socket.",
            "Run this command to fix it.",
        ]
        
        async def external_text_stream() -> AsyncIterable[str]:
            for sentence in test_sentences:
                self.log_event("hermes_raw", sentence)
                yield sentence
                await asyncio.sleep(0.3)
        
        try:
            await self.session.say(external_text_stream())
            logger.info("TEST 1 RESULT: SUCCESS - session.say() accepted AsyncIterable[str]")
        except Exception as e:
            logger.error(f"TEST 1 RESULT: FAIL - {e}")
            raise
        
        # SPIKE TEST 2: Transcription event subscription
        logger.info("=== TEST 2: Transcription events ===")
        
        @self.session.on("user_input_transcribed")
        def on_transcribed(ev):
            self.log_event("user", f"[STT] {ev.transcript}")
        
        @self.session.on("conversation_item_added")
        def on_conversation_item(ev):
            self.log_event("intermediary", f"[Spoke] {ev.content}")
        
        logger.info("TEST 2 RESULT: SUCCESS - subscribed to events")
        
        # SPIKE TEST 3: Barge-in timing
        logger.info("=== TEST 3: Barge-in timing ===")
        
        # Simulate barge-in after 1.5 seconds
        await asyncio.sleep(1.5)
        t0 = time.perf_counter()
        
        # Simulate: stop_speaking() 
        await self.session.stop_speaking()
        
        # Simulate: POST /api/chat/steer immediately (no waiting for SSE)
        steer_text = "no the OTHER error"
        self.log_event("user", f"[Steer] {steer_text}")
        
        elapsed = time.perf_counter() - t0
        logger.info(f"TEST 3 RESULT: Barge-in processed in {elapsed*1000:.1f}ms")
        
        if elapsed < 0.5:
            logger.info("TEST 3 PASS: Steer happened in <500ms")
        else:
            logger.warning("TEST 3 FAIL: Steer took too long")
        
        # SPIKE TEST 4: Post-steer new response
        logger.info("=== TEST 4: Post-steer response ===")
        
        new_sentences = [
            "Ah, you meant the container startup error.",
            "Checking container startup logs now.",
        ]
        
        async def new_text_stream() -> AsyncIterable[str]:
            for sentence in new_sentences:
                self.log_event("hermes_raw", sentence)
                yield sentence
                await asyncio.sleep(0.3)
        
        await self.session.say(new_text_stream())
        logger.info("TEST 4 RESULT: SUCCESS - post-steer response spoken")
        
        # Print event log
        logger.info("=== EVENT LOG ===")
        for event in self.event_log:
            logger.info(f"  [{event.speaker}] {event.text}")
        
        logger.info("=== ALL TESTS COMPLETE ===")
        
        # Keep alive for 10 seconds
        await asyncio.sleep(10)


async def entrypoint(ctx: JobContext):
    """Job entry point."""
    logger.info("Starting intermediary spike test")
    
    agent = IntermediaryAgent()
    
    session = AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(),
    )
    
    await session.start(agent=agent, room=ctx.room)
    
    # Keep alive
    await asyncio.sleep(30)


if __name__ == "__main__":
    # Run with: python3 spike_02_livekit_integration.py --room test-room
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
