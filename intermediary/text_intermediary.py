"""TextIntermediary — the core text MVP.

The intermediary is a thin proxy between user and Hermes:
- System prompt tells it who it is
- If the user asks about the intermediary → answer directly from system prompt
- Otherwise → forward to Hermes, stream the response, distill, emit
"""

import asyncio
import logging
import re
import time
from typing import AsyncIterable, Optional

from .hermes_client import HermesClient
from .distillation import DistillationBuffer, distill, _is_reasoning
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
    
    # The system prompt tells the intermediary who it is.
    SYSTEM_PROMPT = """You are the Intermediary Agent.

## Identity
- Model: qwen2.5:7b-distill (local via Ollama)
- Between: the user and Hermes (LongCat-2.0, custom provider)
- Host: Sydney, NSW, Australia

## Job
- Refine the user's messy speech into clear prompts for Hermes
- Distill Hermes's long technical responses into 1-2 natural sentences
- When the user asks about YOU (the intermediary), answer from this prompt

## Rules
- Keep distilled output for speech: 1-2 natural sentences max
- If the user interrupts, stop and listen
"""
    
    async def chat(self, message: str, stream_id: Optional[str] = None) -> AsyncIterable[IntermediaryEvent]:
        """
        Process a user message:
        1. Refine input
        2. If question is about the intermediary → answer from system prompt
        3. Otherwise → forward to Hermes, stream, distill, emit
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
        
        # 2. Is this a meta-question about the intermediary?
        meta_answer = self._meta_answer(message)
        if meta_answer:
            yield IntermediaryEvent(
                speaker=Speaker.AGENT_SPEAKING,
                text=meta_answer,
                timestamp=time.time(),
                emotion=Emotion.NEUTRAL,
                is_answer=True,
            )
            yield IntermediaryEvent(speaker=Speaker.SYSTEM, text="done", timestamp=time.time())
            return
        
        # 3. Start Hermes run
        if stream_id is None:
            stream_id = await self.hermes.start_chat(refined, self.session_id)
        
        # Stream Hermes response
        buffer = DistillationBuffer()
        hermes_full_text = ""
        
        async for delta in self.hermes.stream_chat(stream_id):
            if self._barge_in_sm.should_drop_delta():
                continue
            hermes_full_text += delta
            sentence = buffer.feed(delta)
            if sentence:
                yield IntermediaryEvent(
                    speaker=Speaker.HERMES,
                    text=sentence,
                    timestamp=time.time(),
                    emotion=Emotion.THINKING,
                    is_reasoning=_is_reasoning(sentence),
                )
        
        final = buffer.flush()
        if final:
            hermes_full_text += " " + final
            yield IntermediaryEvent(
                speaker=Speaker.HERMES,
                text=final,
                timestamp=time.time(),
                emotion=Emotion.THINKING,
                is_reasoning=_is_reasoning(final),
            )
        
        # Distill
        distilled = distill(hermes_full_text)
        if distilled:
            yield IntermediaryEvent(
                speaker=Speaker.AGENT_SPEAKING,
                text=distilled,
                timestamp=time.time(),
                emotion=Emotion.NEUTRAL,
                is_answer=True,
            )
        
        self._barge_in_sm.on_hermes_finish()
        yield IntermediaryEvent(speaker=Speaker.SYSTEM, text="done", timestamp=time.time())
    
    def _meta_answer(self, message: str) -> Optional[str]:
        """
        If the user is asking about the intermediary, answer directly.
        Otherwise return None (forward to Hermes).
        """
        msg = message.lower().strip()
        
        # Only match explicit "about you" questions
        about_you_patterns = [
            r'\b(what|who|which)\s+(are|is)\s+(you|this|the\s*intermediary)',
            r'\bwhat\s+model\s+(are|do)\s+(you|the\s*intermediary)',
            r'\bwho\s+(are|r)\s+you\b',
            r'\babout\s+(you|the\s*intermediary)',
            r'\bwhat\s+(is|are)\s+(the\s*intermediary|your)\s*(model|name|llm)',
            r'\btell\s+me\s+about\s+(yourself|you|the\s*intermediary)',
        ]
        
        for pat in about_you_patterns:
            if re.search(pat, msg):
                return "I'm the Intermediary Agent — running on qwen2.5:7b-distill via Ollama, local on this machine. I sit between you and Hermes, refining your speech and distilling Hermes's responses."
        
        return None
    
    async def steer(self, text: str) -> dict:
        self._barge_in_sm.on_user_speech(text)
        result = await self.hermes.steer(self.session_id, text)
        return result
    
    def _refine(self, text: str) -> str:
        pattern = re.compile(r'^(?:(?:um+|so+|like+|you know+)\s*)+', flags=re.IGNORECASE)
        refined = pattern.sub('', text)
        refined = re.sub(r'^,\s*', '', refined)
        return refined.strip() or text.strip()
