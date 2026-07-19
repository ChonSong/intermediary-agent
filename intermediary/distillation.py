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
        if '\n' in text:
            return True
        return False


def strip_markdown(text: str) -> str:
    """Strip markdown formatting for spoken text."""
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text


def _is_reasoning(text: str) -> bool:
    """Heuristic: detect if text is internal reasoning rather than a direct answer."""
    text_lower = text.lower().strip()
    if not text_lower:
        return False
    # Common reasoning prefixes from LongCat / Claude models
    reasoning_prefixes = [
        'the user is ',
        'the user wants',
        'they want to ',
        'they\'re asking',
        'this is a ',
        'this question ',
        'let me ',
        'i should ',
        'i\'ll ',
        'i need to ',
        'first, ',
        'next, ',
        'however, ',
        'actually, ',
        'looks like ',
        'appears to be ',
        'doesn\'t require ',
        'doesn\'t need ',
        'simple question',
        'trivial question',
        'straightforward ',
        'i can answer',
        'i\'ll answer',
        'i should answer',
        'no need for',
        'the answer is straightforward',
        'succinct response',
        'keep it brief',
        'i\'ll respond',
        'i should respond',
        'i can respond',
        'i need to respond',
        'it directly',
        'promptly',
        'correct answer to',
        'i\'ve determined',
        'based on the',
        'given the context',
    ]
    for prefix in reasoning_prefixes:
        if text_lower.startswith(prefix):
            return True
    # Also detect reasoning by shape: "The X is/are Y. This is/are Z. I should/need/ll..."
    if re.search(r'\b(i|i\'ll|i\'m|let me|the user|this is)', text_lower):
        if re.search('\b(should|need to|will|going to|must|have to)\b', text_lower):
            return True
    return False


async def distill(raw_text: str) -> str:
    """
    Rewrite a raw Hermes response sentence for natural speech.
    
    Phase 1: rule-based heuristic — filter reasoning, strip markdown.
    Phase 1.3+: uses LLM via LiveKit's LLM Output Replacement recipe.
    """
    text = strip_markdown(raw_text)
    # Strip tool use JSON (simplified)
    text = re.sub(r'\{[^}]*"tool"[^}]*\}', '', text)
    
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if not sentences:
        return ''
    
    # Filter out reasoning sentences
    answer_sentences = [s for s in sentences if not _is_reasoning(s)]
    
    # If all sentences were reasoning, return empty (no answer to speak)
    if not answer_sentences:
        return ''
    
    # Keep first 2 answer sentences
    text = ' '.join(answer_sentences[:2])
    return text.strip()
