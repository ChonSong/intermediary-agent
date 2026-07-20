"""Distillation buffer and reasoning filter."""

import re
from typing import Optional


class DistillationBuffer:
    def __init__(self):
        self.buffer = ""
    
    def feed(self, delta: str) -> Optional[str]:
        self.buffer += delta
        if self._has_sentence_boundary(self.buffer):
            sentence = self.buffer.strip()
            self.buffer = ""
            return sentence
        return None
    
    def flush(self) -> Optional[str]:
        if self.buffer.strip():
            result = self.buffer.strip()
            self.buffer = ""
            return result
        return None
    
    @staticmethod
    def _has_sentence_boundary(text: str) -> bool:
        if not text:
            return False
        stripped = text.rstrip()
        if stripped and stripped[-1] in '.!?':
            return True
        if stripped and stripped[-1] == ':':
            return True
        if len(stripped) > 150:
            return True
        if '\n' in text:
            return True
        return False


def distill(raw_text: str) -> str:
    """
    Extract the answer from a Hermes response.
    
    Strategy: reasoning comes first, answer comes last.
    Take the last 1-2 non-trivial sentences.
    """
    text = raw_text.strip()
    if not text:
        return ""
    
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return ""
    
    def is_trivial(s):
        return len(s) < 10
    
    non_trivial = [s for s in sentences if not is_trivial(s)]
    
    if not non_trivial:
        return sentences[-1] if sentences else ""
    
    answer = non_trivial[-2:] if len(non_trivial) >= 2 else non_trivial[-1:]
    result = " ".join(answer)
    
    result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
    result = re.sub(r'\*([^*]+)\*', r'\1', result)
    
    return result.strip()
