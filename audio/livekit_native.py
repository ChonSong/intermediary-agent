"""LiveKit native audio backend.

Uses LiveKit's built-in STT (Deepgram Nova-3) and TTS (Cartesia Sonic-3).
WebRTC transport handles echo cancellation, jitter buffering, and network resilience.
"""

from typing import AsyncIterable
from .base import AudioBackend, TurnEvent, AudioBackendConfig


class LiveKitAudioBackend(AudioBackend):
    """LiveKit-based audio backend for browser voice.
    
    LiveKit handles:
    - WebRTC transport (encrypted, low-latency audio)
    - STT (speech-to-text) via Deepgram Nova-3
    - TTS (text-to-speech) via Cartesia Sonic-3
    - VAD (voice activity detection)
    - Echo cancellation
    - Jitter buffering
    """
    
    def __init__(self, config: AudioBackendConfig = None):
        self.config = config or AudioBackendConfig()
    
    async def start_listening(self) -> AsyncIterable[bytes]:
        """Yield audio chunks from LiveKit microphone track."""
        # In production, this reads from LiveKit room's local audio track
        raise NotImplementedError("Requires LiveKit room connection")
    
    async def speak(self, audio: AsyncIterable[bytes]) -> None:
        """Play audio via LiveKit speaker track."""
        # In production, this publishes to LiveKit room's speaker track
        raise NotImplementedError("Requires LiveKit room connection")
    
    async def stop_speaking(self) -> None:
        """Stop LiveKit audio playback."""
        raise NotImplementedError("Requires LiveKit room connection")
    
    async def detect_turn(self, audio_stream: AsyncIterable[bytes]) -> AsyncIterable[TurnEvent]:
        """Detect turn boundaries using LiveKit VAD."""
        raise NotImplementedError("Requires LiveKit room connection")
    
    async def close(self) -> None:
        """Disconnect from LiveKit room."""
        pass
