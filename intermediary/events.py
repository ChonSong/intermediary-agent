"""Intermediary events — structured events for UI and future audio."""

from dataclasses import dataclass, field
from typing import Optional


class Speaker:
    USER = "user"
    INTERMEDIARY = "intermediary"
    HERMES = "hermes_raw"
    AGENT_SPEAKING = "agent_speaking"
    SYSTEM = "system"


class Emotion:
    NEUTRAL = "neutral"
    THINKING = "thinking"
    HAPPY = "happy"
    CONFUSED = "confused"


@dataclass
class IntermediaryEvent:
    speaker: str
    text: str
    timestamp: float
    emotion: Optional[str] = None
    audio: Optional[bytes] = None
    generation: int = 0
    is_reasoning: bool = False
    is_answer: bool = False
    
    def to_dict(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "timestamp": self.timestamp,
            "emotion": self.emotion,
            "is_reasoning": self.is_reasoning,
            "is_answer": self.is_answer,
        }
