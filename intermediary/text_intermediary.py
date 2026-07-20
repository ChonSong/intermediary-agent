"""TextIntermediary — core text MVP."""

import asyncio
import logging
import re
import time
from typing import AsyncIterable, Optional

from .hermes_client import HermesClient
from .distillation import DistillationBuffer, distill
from .steering import BargeInStateMachine
from .events import IntermediaryEvent, Speaker, Emotion

logger = logging.getLogger(__name__)


class TextIntermediary:
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
        Streaming strategy:
        1. Refine input
        2. Accumulate Hermes SSE deltas into sentences
        3. Emit each sentence as HERMES reasoning (visible in UI)
        4. After stream completes, distill ALL accumulated text
        5. Emit the distilled answer as AGENT_SPEAKING (final answer)
        
        This gives transparency — user sees both reasoning AND a clean final summary.
        """
        timestamp = time.time()
        
        # Auto-create session if using default
        if self.session_id == "default":
            try:
                self.session_id = await self.hermes.create_session()
            except Exception:
                pass
        
        # 1. Refine
        refined = self._refine(message)
        yield IntermediaryEvent(
            speaker=Speaker.INTERMEDIARY,
            text=refined,
            timestamp=timestamp,
            emotion=Emotion.THINKING,
        )
        
        # 2. Start Hermes run
        if stream_id is None:
            stream_id = await self.hermes.start_chat(refined, self.session_id)
        
        # 3. Stream Hermes response → emit reasoning sentences as they come
        buffer = DistillationBuffer()
        hermes_full_text = ""
        
        async for delta in self.hermes.stream_chat(stream_id):
            if self._barge_in_sm.should_drop_delta():
                continue
            
            hermes_full_text += delta
            
            # Emit each sentence as HERMES reasoning
            sentence = buffer.feed(delta)
            if sentence:
                yield IntermediaryEvent(
                    speaker=Speaker.HERMES,
                    text=sentence,
                    timestamp=time.time(),
                    emotion=Emotion.THINKING,
                    is_reasoning=True,
                )
        
        # Flush remaining buffer
        final = buffer.flush()
        if final:
            hermes_full_text += " " + final
            yield IntermediaryEvent(
                speaker=Speaker.HERMES,
                text=final,
                timestamp=time.time(),
                emotion=Emotion.THINKING,
                is_reasoning=True,
            )
        
        # 4. Distill the full response
        distilled = distill(hermes_full_text)
        
        if distilled:
            yield IntermediaryEvent(
                speaker=Speaker.AGENT_SPEAKING,
                text=distilled,
                timestamp=time.time(),
                emotion=Emotion.NEUTRAL,
                is_answer=True,
            )
        
        # 5. Done
        self._barge_in_sm.on_hermes_finish()
        yield IntermediaryEvent(
            speaker=Speaker.SYSTEM,
            text="done",
            timestamp=time.time(),
        )
    
    async def steer(self, text: str) -> dict:
        self._barge_in_sm.on_user_speech(text)
        result = await self.hermes.steer(self.session_id, text)
        return result
    
    def _refine(self, text: str) -> str:
        import re
        pattern = re.compile(r'^(?:(?:um+|so+|like+|you know+)\s*)+', flags=re.IGNORECASE)
        refined = pattern.sub('', text)
        refined = re.sub(r'^,\s*', '', refined)
        return refined.strip() or text.strip()
