"""Intermediary events — structured events for emotion-avatar extension point.

The intermediary emits these events so any renderer can subscribe:
- LiveKit TTS: consumes text → audio
- Transcript UI: consumes text → display
- Emotion-avatar (future): consumes emotion+text → animation
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class Speaker(Enum):
    USER = "user"
    HERMES = "hermes_raw"
    INTERMEDIARY = "intermediary"
    AGENT_SPEAKING = "agent_speaking"
    SYSTEM = "system"


class Emotion(Enum):
    """Emotion hints for future avatar renderer."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    THINKING = "thinking"
    SURPRISED = "surprised"
    CONFUSED = "confused"


@dataclass
class IntermediaryEvent:
    """Structured event emitted by the intermediary agent.
    
    Can be consumed by:
    - LiveKit TTS (text → audio frames)
    - Transcript UI (text → DOM elements)
    - Emotion-avatar (emotion + text → animation state)
    """
    speaker: Speaker
    text: str
    timestamp: float
    emotion: Optional[Emotion] = None
    audio: Optional[bytes] = None  # raw audio for lip-sync
    generation: int = 0  # increments on barge-in
    
    def to_dict(self):
        return {
            "speaker": self.speaker.value,
            "text": self.text,
            "timestamp": self.timestamp,
            "emotion": self.emotion.value if self.emotion else None,
            "generation": self.generation,
        }
