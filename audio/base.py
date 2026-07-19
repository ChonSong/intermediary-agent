"""AudioBackend ABC for pluggable audio IO.

The intermediary itself does NOT produce audio. But for full-duplex voice
(user speaks while agent speaks, barge-in, turn-taking), plug in a swappable
audio backend.

Backends:
- livekit_native: LiveKit built-in STT/TTS (default for browser)
- ten: TEN Turn Detection (better barge-in)
- pipecat: Pipecat concurrent pipeline (lower latency)
- discord: Discord VC bridge
- mock: For testing
"""

from abc import ABC, abstractmethod
from typing import AsyncIterable, Optional
from dataclasses import dataclass
from enum import Enum


class TurnEvent(Enum):
    USER_SPEAKING = "user_speaking"
    USER_SILENT = "user_silent"
    USER_DONE = "user_done"  # end of turn detected


@dataclass
class AudioBackendConfig:
    sample_rate: int = 16000
    channels: int = 1
    frame_duration_ms: int = 20
    vad_sensitivity: float = 0.5


class AudioBackend(ABC):
    """Pluggable audio IO for full-duplex voice.
    
    The intermediary calls these methods to:
    1. Listen to user speech (raw audio chunks)
    2. Speak agent responses (play audio)
    3. Handle barge-in (stop speaking immediately)
    4. Detect turn boundaries (when user is done speaking)
    """
    
    @abstractmethod
    async def start_listening(self) -> AsyncIterable[bytes]:
        """Start streaming raw audio chunks from user microphone.
        
        Yields raw PCM audio bytes.
        """
        ...
    
    @abstractmethod
    async def speak(self, audio: AsyncIterable[bytes]) -> None:
        """Play audio to user.
        
        Takes an async stream of PCM audio chunks.
        Should support interruption via stop_speaking().
        """
        ...
    
    @abstractmethod
    async def stop_speaking(self) -> None:
        """Barge-in: immediately stop playback when user starts talking."""
        ...
    
    @abstractmethod
    async def detect_turn(self, audio_stream: AsyncIterable[bytes]) -> AsyncIterable[TurnEvent]:
        """Yield TurnEvent stream from audio.
        
        - USER_SPEAKING: VAD detected user speech
        - USER_SILENT: VAD detected silence
        - USER_DONE: Turn detection determined end of user turn
        """
        ...
    
    @abstractmethod
    async def close(self) -> None:
        """Cleanup resources."""
        ...
