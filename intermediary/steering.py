"""Barge-in state machine for user-initiated steering."""

import time
from typing import Optional


class BargeInStateMachine:
    """
    States: LISTENING → SPEAKING → STALE → INJECT → SPEAKING
    
    Critical: Steer must happen IMMEDIATELY when VAD detects interrupt,
    NOT after SSE ends. If SSE ends, the agent run completes and
    /api/chat/steer returns {"accepted": false, "fallback": "stream_dead"}.
    """
    
    LISTENING = "LISTENING"
    SPEAKING = "SPEAKING"
    STALE = "STALE"
    INJECT = "INJECT"
    
    def __init__(self):
        self.state = self.LISTENING
        self.pending_steer: Optional[str] = None
        self.steer_active = False
        self.generation = 0
        self._steer_posted_at: Optional[float] = None
        self._vad_detected_at: Optional[float] = None
    
    def on_user_speech(self, text: str):
        """User speech committed. If we were speaking → barge-in."""
        if self.state == self.SPEAKING:
            # Barge-in detected
            self._vad_detected_at = time.perf_counter()
            self.state = self.STALE
            self.pending_steer = text
            self.steer_active = True
            self.generation += 1
            # CRITICAL: POST /api/chat/steer IMMEDIATELY
            self._steer_posted_at = time.perf_counter()
        elif self.state == self.LISTENING:
            # Normal turn
            self.state = self.SPEAKING
    
    def on_hermes_finish(self):
        """Hermes finished current step."""
        if self.state == self.STALE:
            self.state = self.INJECT
        elif self.state == self.SPEAKING:
            # Normal end of turn
            self.state = self.LISTENING
    
    def on_new_response(self):
        """Hermes starts generating new response (after steer applied)."""
        if self.state == self.INJECT:
            self.steer_active = False
            self.pending_steer = None
            self.state = self.SPEAKING
    
    def should_drop_delta(self) -> bool:
        """Drop deltas from old context after barge-in."""
        return self.steer_active
