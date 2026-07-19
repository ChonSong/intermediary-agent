"""Configuration for the intermediary agent."""

from pydantic import BaseModel, Field
from typing import Optional


class LiveKitConfig(BaseModel):
    url: str = "ws://localhost:7880"
    api_key: str = "devkey"
    api_secret: str = "secret"


class HermesConfig(BaseModel):
    url: str = "http://localhost:3000"
    api_key: Optional[str] = None


class AudioConfig(BaseModel):
    backend: str = "livekit"
    barge_in: bool = True
    turn_detection: bool = True
    stt_provider: str = "deepgram"
    stt_model: str = "nova-3"
    tts_provider: str = "cartesia"
    tts_model: str = "sonic-3"


class IntermediaryConfig(BaseModel):
    hermes: HermesConfig = Field(default_factory=HermesConfig)
    livekit: LiveKitConfig = Field(default_factory=LiveKitConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    enabled: bool = True
    silence_ms: int = 1800
    max_steer_per_exchange: int = 1
