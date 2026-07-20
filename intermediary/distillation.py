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


def _is_reasoning(sentence: str) -> bool:
    """Detect if a sentence is internal reasoning, not a direct answer."""
    s = sentence.lower().strip()
    if len(s) < 5:
        return False
    
    # Strong reasoning indicators
    reasoning_patterns = [
        r'^the user (is|wants|asked|just|said|typed)',
        r'^this is (a |an |the )',
        r'^they (want|are|were|just|asked)',
        r'^let me ',
        r'^i should ',
        r'^i\'ll ',
        r'^i need to ',
        r'^first,',
        r'^next,',
        r'^however,',
        r'^actually,',
        r'^looks like ',
        r'^appears to be ',
        r'^doesn\'t require ',
        r'^doesn\'t need ',
        r'^simple question',
        r'^trivial question',
        r'^straightforward ',
        r'^i can answer',
        r'^i\'ll answer',
        r'^i should answer',
        r'^no need for',
        r'^the answer is straightforward',
        r'^succinct response',
        r'^keep it brief',
        r'^i\'ll respond',
        r'^i should respond',
        r'^i can respond',
        r'^i need to respond',
        r'^i should also',
        r'^i\'ve determined',
        r'^based on the',
        r'^given the context',
        r'^check the ',
        r'^hermes agent',
        r'^hermes agent skill',
        r'^looking at your',
        r'^the user just',
        r'^no need for',
        r'^no need to',
        r'^just said',
        r'^simple greeting',
        r'^without overdoing',
        r'^i\'ll just',
        r'^i can just',
        r'^i should just',
        r'^the user\'s (question|request|message)',
        r'^they\'re asking',
        r'^they are asking',
        r'^this (question|request|is|seems|appears)',
        r'^it\'s (a |an |important|necessary|clear)',
        r'^there\'s (no |a |still |nothing )',
        r'^we (can |should |need to |have to )',
        r'^you (can |should |need to |might |could |may |would )',
        r'^i should (just|also|be|have|make|take|give|try|check|verify|confirm|consider|think|look|review|recheck|double-check|ensure)',
        r'^i\'ll (just|also|be|have|make|take|give|try|check|verify|confirm|consider|think|look|review|recheck|double-check|ensure)',
        r'^i (can|could|might|may|must|need to|want to|have to|should|will) (just|also|be|have|make|take|give|try|check|verify|confirm|consider|think|look|review|recheck|double-check|ensure)',
    ]
    
    for pattern in reasoning_patterns:
        if re.match(pattern, s):
            return True
    
    # Sentence shape: contains "I/let me/the user" AND an action verb
    if re.search(r'\b(i|i\'ll|i\'m|let me|the user|this is|they)\b', s):
        if re.search(r'\b(should|need to|will|going to|must|have to|could|might|let me|check|look|find|respond|answer|think|consider)\b', s):
            return True
    
    return False


def distill(raw_text: str) -> str:
    """
    Extract the answer from a Hermes response.
    
    Strategy: 
    1. Split into sentences
    2. Mark each sentence as reasoning or answer
    3. Find the LAST CONTIGUOUS BLOCK of answer sentences
    4. If the block is very short (e.g., "4"), extend one sentence back to capture context
    
    The actual answer is almost always at the end, after all the reasoning.
    """
    text = raw_text.strip()
    if not text:
        return ""
    
    # Split into sentences (handle newlines too)
    raw_sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
    # Further split on period followed by capital letter
    sentences = []
    for s_in in raw_sentences:
        for s in re.split(r'(?<=[.])(?=[A-Z])', s_in):
            s = s.strip()
            if s:
                sentences.append(s)
    
    if not sentences:
        return ""
    
    # Classify each sentence
    classified = [(s, _is_reasoning(s)) for s in sentences]
    
    # Find the last contiguous block of non-reasoning sentences
    last_block = []
    for s, is_reversed in reversed(classified):
        if is_reversed:
            break
        last_block.insert(0, s)
    
    # If everything was reasoning, take the shortest (usually a trailing answer)
    if not last_block:
        shortest = min(sentences, key=len)
        return shortest.strip()
    
    # If last block is very short and there's more content, it might be an isolated answer
    # like "4" — capture just that
    result = " ".join(last_block)
    
    # Strip markdown
    result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
    result = re.sub(r'\*([^*]+)\*', r'\1', result)
    
    return result.strip()
