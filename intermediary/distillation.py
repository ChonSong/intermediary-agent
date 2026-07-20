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
    if len(s) < 3:
        return False
    
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
        r'^provider config',
        r'^- ',
        r'^pool:',
        r'^skill-',
        r'^cred',
    ]
    
    for pattern in reasoning_patterns:
        if re.match(pattern, s):
            return True
    
    # Sentence shape: contains "I/let me/the user" AND an action verb
    if re.search(r'\b(i|i\'ll|i\'m|let me|the user|this is|they)\b', s):
        if re.search(r'\b(should|need to|will|going to|must|have to|could|might|let me|check|look|find|respond|answer|think|consider)\b', s):
            return True
    
    return False


def _strip_answer_prefix(text: str) -> str:
    """Strip reasoning-like prefixes from the start of an answer."""
    s = text.strip()
    # "From the context:" 
    s = re.sub(r'^from the context:\s*', '', s, flags=re.IGNORECASE)
    # "I'm running on X" → keep, this is the answer
    # "The answer is X" → strip prefix
    s = re.sub(r'^the answer is\s*', '', s, flags=re.IGNORECASE)
    # "I think X" → strip prefix
    s = re.sub(r'^i think\s+', '', s, flags=re.IGNORECASE)
    # "Let me tell you:" 
    s = re.sub(r'^let me tell you:\s*', '', s, flags=re.IGNORECASE)
    # Strip leading quotes
    s = re.sub(r'^["\']+', '', s)
    return s.strip()


def distill(raw_text: str) -> str:
    """
    Extract the answer from a Hermes response.
    
    Strategy:
    1. Split into sentences
    2. Filter out reasoning + metadata sentences
    3. Take the LAST non-reasoning sentence (the direct answer)
    4. Strip reasoning prefixes
    """
    text = raw_text.strip()
    if not text:
        return ""
    
    # Split into sentences (handle newlines too)
    raw_sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
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
    
    # Find ALL non-reasoning sentences with their indices
    answer_sentences = [(i, s) for i, (s, is_rev) in enumerate(classified) if not is_rev]
    
    if not answer_sentences:
        # All reasoning - return the shortest sentence
        shortest = min(sentences, key=len)
        return _strip_answer_prefix(shortest.strip())
    
    # Take the LAST 1-2 non-reasoning sentences
    # The answer is almost always at the end
    last_idx, last_s = answer_sentences[-1]
    
    # If the second-to-last is also close and short, include it
    result = last_s
    if len(answer_sentences) >= 2:
        prev_idx, prev_s = answer_sentences[-2]
        if last_idx - prev_idx <= 2 and len(prev_s) < 60:
            result = prev_s + " " + last_s
    
    # Strip markdown
    result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
    result = re.sub(r'\*([^*]+)\*', r'\1', result)
    
    # Strip reasoning prefixes
    result = _strip_answer_prefix(result)
    
    return result.strip()
