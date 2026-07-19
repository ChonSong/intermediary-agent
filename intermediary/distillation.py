"""Distillation buffer and markdown stripping for spoken text."""

import re
from typing import Optional


class DistillationBuffer:
    """
    Accumulates SSE deltas (1-4 chars) until sentence boundary.
    Then emits the complete sentence for distillation.
    
    Rationale: You cannot pass sub-word tokens to an LLM for rewriting.
    The LLM needs a complete semantic thought to rewrite for speech.
    """
    
    def __init__(self):
        self.buffer = ""
    
    def feed(self, delta: str) -> Optional[str]:
        """Feed an SSE delta. Returns complete sentence when boundary hit."""
        self.buffer += delta
        if self._has_sentence_boundary(self.buffer):
            sentence = self.buffer.strip()
            self.buffer = ""
            return sentence
        return None
    
    def flush(self) -> Optional[str]:
        """Force-emit whatever is in the buffer (at stream end)."""
        if self.buffer.strip():
            result = self.buffer.strip()
            self.buffer = ""
            return result
        return None
    
    @staticmethod
    def _has_sentence_boundary(text: str) -> bool:
        """Detect sentence/clause boundary."""
        if not text:
            return False
        stripped = text.rstrip()
        # Sentence terminators
        if stripped and stripped[-1] in '.!?':
            return True
        if stripped and stripped[-1] == ':':
            return True
        # Safety yield: >150 chars without punctuation — force emit
        if len(stripped) > 150:
            return True
        # Newline boundary (paragraph breaks)
        if '\n' in stripped:
            return True
        return False


def strip_markdown(text: str) -> str:
    """Strip markdown formatting for spoken text."""
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text


async def distill(raw_text: str) -> str:
    """
    Rewrite a raw Hermes response sentence for natural speech.
    
    Phase 1: rule-based heuristic (strip markdown, keep first 1-2 sentences).
    Phase 1.3+: uses LLM via LiveKit's LLM Output Replacement recipe.
    """
    text = strip_markdown(raw_text)
    # Strip tool use JSON (simplified)
    text = re.sub(r'\{[^}]*"tool"[^}]*\}', '', text)
    # Keep first 1-2 sentences
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if len(sentences) > 2:
        text = ' '.join(sentences[:2])
    return text.strip()
