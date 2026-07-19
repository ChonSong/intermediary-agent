"""TextIntermediary — the core text-only MVP.

Wires together:
- Refinement (system prompt / placeholder)
- HermesClient (HTTP/SSE to Hermes API)
- DistillationBuffer (sentence boundary detection)
- distill() (rewrite for speech)

Yields IntermediaryEvent objects for any consumer (FastAPI SSE, CLI, etc.)
"""

import asyncio
import logging
import time
from typing import AsyncIterable, Optional

from .hermes_client import HermesClient
from .distillation import DistillationBuffer, distill
from .steering import BargeInStateMachine
from .events import IntermediaryEvent, Speaker, Emotion

logger = logging.getLogger(__name__)


class TextIntermediary:
    """
    Text-only intermediary — no LiveKit, no voice.
    
    Usage:
        intermediary = TextIntermediary(hermes_client, session_id="ses-123")
        async for event in intermediary.chat("um the docker thing?"):
            print(event.speaker, event.text)
    """
    
    def __init__(
        self,
        hermes_client: HermesClient,
        session_id: str = "default",
    ):
        self.hermes = hermes_client
        self.session_id = session_id
        self._barge_in_sm = BargeInStateMachine()
    
    async def chat(self, message: str, stream_id: Optional[str] = None) -> AsyncIterable[IntermediaryEvent]:
        """
        Process a user message through the full pipeline.
        
        Args:
            message: Raw user input
            stream_id: If provided, use this stream_id instead of starting a new chat
            
        Yields:
        - refined: the clarified user input
        - hermes_raw: the full Hermes response (accumulated)
        - distilled: each distilled sentence
        - done: when Hermes finishes
        """
        timestamp = time.time()
        
        # Auto-create session if using default
        if self.session_id == "default":
            try:
                self.session_id = await self.hermes.create_session()
            except Exception:
                pass  # Mock might not have create_session
        
        # 1. Refine
        refined = self._refine(message)
        yield IntermediaryEvent(
            speaker=Speaker.INTERMEDIARY,
            text=refined,
            timestamp=timestamp,
            emotion=Emotion.THINKING,
        )
        
        # 2. Start Hermes run (or use provided stream_id)
        if stream_id is None:
            stream_id = await self.hermes.start_chat(refined, self.session_id)
        
        # 3. Stream Hermes response → buffer → distill
        buffer = DistillationBuffer()
        hermes_full_text = ""
        
        async for delta in self.hermes.stream_chat(stream_id):
            # Check for barge-in
            if self._barge_in_sm.should_drop_delta():
                continue
            
            hermes_full_text += delta
            
            # Buffer and check for sentence boundary
            sentence = buffer.feed(delta)
            if sentence:
                # Yield the raw Hermes text
                yield IntermediaryEvent(
                    speaker=Speaker.HERMES,
                    text=sentence,
                    timestamp=time.time(),
                )
                
                # Distill and yield
                distilled = await distill(sentence)
                if distilled:
                    yield IntermediaryEvent(
                        speaker=Speaker.AGENT_SPEAKING,
                        text=distilled,
                        timestamp=time.time(),
                        emotion=Emotion.NEUTRAL,
                    )
        
        # Flush remaining buffer
        final = buffer.flush()
        if final:
            yield IntermediaryEvent(
                speaker=Speaker.HERMES,
                text=final,
                timestamp=time.time(),
            )
            distilled = await distill(final)
            if distilled:
                yield IntermediaryEvent(
                    speaker=Speaker.AGENT_SPEAKING,
                    text=distilled,
                    timestamp=time.time(),
                    emotion=Emotion.NEUTRAL,
                )
        
        # 4. Done
        self._barge_in_sm.on_hermes_finish()
        yield IntermediaryEvent(
            speaker=Speaker.SYSTEM,
            text="done",
            timestamp=time.time(),
        )
    
    async def steer(self, text: str) -> dict:
        """Inject steer into active Hermes run."""
        self._barge_in_sm.on_user_speech(text)
        result = await self.hermes.steer(self.session_id, text)
        return result
    
    def _refine(self, text: str) -> str:
        """Refine messy input. Phase 1: placeholder. Phase 1.3+: LLM call."""
        import re
        # Remove consecutive filler words from the start (greedy)
        pattern = re.compile(r'^(?:(?:um+|so+|like+|you know+)\s*)+', flags=re.IGNORECASE)
        refined = pattern.sub('', text)
        # Remove leading comma if present
        refined = re.sub(r'^,\s*', '', refined)
        return refined.strip() or text.strip()
