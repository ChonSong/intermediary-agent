"""Mock audio backend for testing.

Simulates microphone input and speaker output without real audio hardware.
"""

import asyncio
from typing import AsyncIterable
from .base import AudioBackend, TurnEvent, AudioBackendConfig


class MockAudioBackend(AudioBackend):
    """Mock audio backend for testing.
    
    - Records speak() calls
    - Can simulate barge-in via trigger_barge_in()
    """
    
    def __init__(self, config: AudioBackendConfig = None):
        self.config = config or AudioBackendConfig()
        self.spoken_chunks: list[bytes] = []
        self._speaking = False
        self._barge_in = asyncio.Event()
    
    async def start_listening(self) -> AsyncIterable[bytes]:
        """Yield preset audio chunks (test data)."""
        return
        yield  # make it an async generator
    
    async def speak(self, audio: AsyncIterable[bytes]) -> None:
        """Record audio chunks instead of playing."""
        self._speaking = True
        async for chunk in audio:
            if self._barge_in.is_set():
                break
            self.spoken_chunks.append(chunk)
        self._speaking = False
    
    async def stop_speaking(self) -> None:
        """Stop speaking immediately."""
        self._barge_in.set()
    
    async def detect_turn(self, audio_stream: AsyncIterable[bytes]) -> AsyncIterable[TurnEvent]:
        """Yield preset turn events."""
        yield TurnEvent.USER_SPEAKING
        yield TurnEvent.USER_DONE
    
    async def close(self) -> None:
        """No-op."""
        pass
    
    def trigger_barge_in(self):
        """Test helper: trigger barge-in."""
        self._barge_in.set()
