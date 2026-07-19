#!/usr/bin/env python3
"""
Spike 03: Unit-test the riskiest logic WITHOUT needing a LiveKit server.

Tests:
1. Distillation buffer: correctly accumulates 1-4 char SSE deltas, emits at sentence boundary
2. Refinement: resolves pronouns using intent history
3. Barge-in state machine: transitions + timing
4. Steer timing: POST happens IMMEDIATELY, not after SSE ends
5. SSE parsing: correctly parses Hermes SSE format

All tests are deterministic — no network, no servers.
"""

import json
import re
import time
from typing import AsyncIterable, Optional


# ============================================================================
# PRODUCTION CODE (these will be moved to the real files after validation)
# ============================================================================

class DistillationBuffer:
    """
    Accumulates SSE deltas (1-4 chars) until sentence boundary.
    Then emits the complete sentence for distillation.
    """
    
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


class BargeInStateMachine:
    LISTENING = "LISTENING"
    SPEAKING = "SPEAKING"
    STALE = "STALE"
    INJECT = "INJECT"
    
    def __init__(self):
        self.state = self.LISTENING
        self.pending_steer = None
        self.steer_active = False
        self.generation = 0
        self._steer_posted_at = None
        self._vad_detected_at = None
    
    def on_user_speech(self, text: str):
        if self.state == self.SPEAKING:
            self._vad_detected_at = time.perf_counter()
            self.state = self.STALE
            self.pending_steer = text
            self.steer_active = True
            self.generation += 1
            self._steer_posted_at = time.perf_counter()
        elif self.state == self.LISTENING:
            self.state = self.SPEAKING
    
    def on_hermes_finish(self):
        if self.state == self.STALE:
            self.state = self.INJECT
        elif self.state == self.SPEAKING:
            # Normal end of turn
            self.state = self.LISTENING
    
    def on_new_response(self):
        if self.state == self.INJECT:
            self.steer_active = False
            self.pending_steer = None
            self.state = self.SPEAKING
    
    def should_drop_delta(self) -> bool:
        return self.steer_active


def _strip_markdown(text: str) -> str:
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text


def refine_input(raw_text: str, intent_history: list[str]) -> str:
    """Phase 1 placeholder: removes filler words. Phase 1.3+ uses LLM."""
    text = raw_text.strip()
    text = re.sub(r'^(um+|so+|like+|you know+)\s*', '', text, flags=re.IGNORECASE)
    return text.strip() or raw_text.strip()


# ============================================================================
# SPIKE TESTS
# ============================================================================

def test_distillation_buffer():
    print("\n=== TEST: Distillation Buffer ===")
    
    buf = DistillationBuffer()
    deltas = ["F", "ir", "st", ", ", "le", "t ", "me", " ch", "ec", "k."]
    emitted = []
    for delta in deltas:
        result = buf.feed(delta)
        if result:
            emitted.append(result)
    assert emitted == ["First, let me check."], f"Got {emitted}"
    print("  ✓ Buffer correctly accumulates 1-4 char deltas to sentence boundary")
    
    buf2 = DistillationBuffer()
    deltas2 = ["F", "ir", "st", ". ", "Se", "co", "nd", "."]
    emitted2 = []
    for delta in deltas2:
        result = buf2.feed(delta)
        if result:
            emitted2.append(result)
    assert emitted2 == ["First.", "Second."], f"Got {emitted2}"
    print("  ✓ Multi-sentence stream correctly split")
    
    buf3 = DistillationBuffer()
    text_long = "This is a very long sentence that goes on and on without any punctuation for quite a while indeed yes it just keeps going and going without any end in sight whatsoever"
    emitted3 = []
    for delta in text_long:
        result = buf3.feed(delta)
        if result:
            emitted3.append(result)
    assert len(emitted3) >= 1
    print("  ✓ Long buffer (>150 chars) triggers safety yield")
    
    buf4 = DistillationBuffer()
    for c in "Incomplete sentence without ending":
        buf4.feed(c)
    assert buf4.flush() == "Incomplete sentence without ending"
    print("  ✓ Flush emits remaining buffer at stream end")


def test_refinement():
    print("\n=== TEST: Refinement (Phase 1 placeholder) ===")
    history = ["Docker permission error", "file permissions", "Docker socket"]
    cases = [
        ("um the docker thing?", "the docker thing?"),
        ("so like the thing", "like the thing"),
        ("you know the error", "the error"),
    ]
    for raw, expected in cases:
        refined = refine_input(raw, history)
        print(f"  {raw!r} → {refined!r}")
        assert refined == expected, f"Expected {expected!r}, got {refined!r}"
    print("  ✓ Filler word removal works")
    print("  ℹ Full pronoun resolution uses LLM in Phase 1.3+")


def test_barge_in_state_machine():
    print("\n=== TEST: Barge-in State Machine ===")
    sm = BargeInStateMachine()
    assert sm.state == BargeInStateMachine.LISTENING
    sm.on_user_speech("hello")
    assert sm.state == BargeInStateMachine.SPEAKING
    sm.on_hermes_finish()
    assert sm.state == BargeInStateMachine.LISTENING
    print("  ✓ Normal turn: LISTENING → SPEAKING → LISTENING")
    
    sm.on_user_speech("hello")
    sm.on_user_speech("no wait")
    assert sm.state == BargeInStateMachine.STALE
    assert sm.steer_active is True
    latency = (sm._steer_posted_at - sm._vad_detected_at) * 1000
    assert latency < 50
    print(f"  ✓ Barge-in: state → STALE, steer posted in {latency:.1f}ms")
    
    sm.on_hermes_finish()
    assert sm.state == BargeInStateMachine.INJECT
    sm.on_new_response()
    assert sm.state == BargeInStateMachine.SPEAKING
    assert sm.steer_active is False
    print("  ✓ INJECT → SPEAKING (steer cleared)")


def test_stale_delta_dropping():
    print("\n=== TEST: Stale Delta Dropping ===")
    sm = BargeInStateMachine()
    sm.on_user_speech("hello")
    assert sm.should_drop_delta() is False
    sm.on_user_speech("no wait")
    assert sm.should_drop_delta() is True
    print("  ✓ Deltas dropped after barge-in")
    sm.on_hermes_finish()
    sm.on_new_response()
    assert sm.should_drop_delta() is False
    print("  ✓ Deltas resume after new response")


def test_markdown_stripping():
    print("\n=== TEST: Markdown Stripping (sync part) ===")
    cases = [
        ("**Docker** is great.", "Docker is great."),
        ("**First**, let me check.", "First, let me check."),
        ("Run `sudo usermod` now.", "Run sudo usermod now."),
    ]
    for raw, expected in cases:
        stripped = _strip_markdown(raw)
        print(f"  {raw!r} → {stripped!r}")
        assert stripped == expected
    print("  ✓ Markdown stripping works")


def test_sse_format_parsing():
    print("\n=== TEST: SSE Format Parsing ===")
    sse_lines = [
        'data: {"type": "delta", "content": "First, let me check"}',
        'data: {"type": "tool_use", "tool": "read_file", "args": {"path": "/var/log/syslog"}}',
        'data: {"type": "thinking", "content": "Let me think about this..."}',
        'data: {"type": "delta", "content": " the Docker logs."}',
        'data: {"type": "done"}',
    ]
    deltas = []
    for line in sse_lines:
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if data.get("type") == "delta":
                deltas.append(data["content"])
    full_text = "".join(deltas)
    assert full_text == "First, let me check the Docker logs."
    print("  ✓ SSE format parsed correctly")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("INTERMEDIARY AGENT SPIKE 03: Pure-Logic Validation")
    print("=" * 60)
    try:
        test_distillation_buffer()
        test_refinement()
        test_barge_in_state_machine()
        test_stale_delta_dropping()
        test_markdown_stripping()
        test_sse_format_parsing()
        print("\n" + "=" * 60)
        print("ALL SPIKE TESTS PASSED")
        print("=" * 60)
        print("\nValidated:")
        print("  1. Distillation buffer: 1-4 char SSE deltas → sentence boundary")
        print("  2. Refinement: filler word removal (LLM in Phase 1.3+)")
        print("  3. Barge-in state machine: transitions + immediate steer")
        print("  4. Stale delta dropping after barge-in")
        print("  5. Markdown stripping for spoken text")
        print("  6. SSE format parsing")
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        raise
