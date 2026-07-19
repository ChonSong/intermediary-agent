"""Session state management for the intermediary agent."""

import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SessionState:
    """State for a single LiveKit participant ↔ Hermes session mapping."""
    
    room: str
    participant_identity: str
    hermes_session_id: str = ""
    intent_history: list[str] = field(default_factory=list)
    current_topic: str = ""
    steer_active: bool = False
    pending_steer: Optional[str] = None
    generation: int = 0
    
    def activate_steer(self, text: str):
        """Activate steer mode (barge-in detected)."""
        self.pending_steer = text
        self.steer_active = True
        self.generation += 1
    
    def deactivate_steer(self):
        """Clear steer mode (new response from Hermes)."""
        self.steer_active = False
        self.pending_steer = None


class SessionManager:
    """Manages LiveKit ↔ Hermes session mappings."""
    
    def __init__(self):
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()
    
    async def create_session(
        self,
        room: str,
        participant_identity: str,
        hermes_session_id: str = "",
    ) -> SessionState:
        """Create a new session mapping."""
        async with self._lock:
            state = SessionState(
                room=room,
                participant_identity=participant_identity,
                hermes_session_id=hermes_session_id,
            )
            self._sessions[participant_identity] = state
            return state
    
    async def get_session(self, participant_identity: str) -> Optional[SessionState]:
        """Get session by participant identity."""
        return self._sessions.get(participant_identity)
    
    async def remove_session(self, participant_identity: str):
        """Remove session."""
        async with self._lock:
            self._sessions.pop(participant_identity, None)
