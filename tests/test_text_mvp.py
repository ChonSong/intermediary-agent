"""
Tests for the text MVP pipeline (TextIntermediary).

Validates:
- Refinement removes filler words
- Chat yields correct IntermediaryEvent objects with proper speaker order
- Distillation produces shorter output than raw Hermes text
- Barge-in during streaming drops remaining deltas
- Stale deltas from old context are silently dropped
- Full pipeline integration end-to-end with mock Hermes
"""

import asyncio

import httpx
import pytest

from intermediary.distillation import DistillationBuffer, distill
from intermediary.events import Emotion, IntermediaryEvent, Speaker
from intermediary.hermes_client import HermesClient
from intermediary.mock_hermes import create_mock_hermes
from intermediary.steering import BargeInStateMachine
from intermediary.text_intermediary import TextIntermediary


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def mock_hermes_app():
    """Create a mock Hermes server with multi-sentence response."""
    return create_mock_hermes(
        response_text="First, let me check the Docker logs. I can see a permission denied error.",
        chunk_size=1,
        chunk_delay=0.001,
    )


@pytest.fixture
def hermes_client(mock_hermes_app):
    """Create a HermesClient wired to the mock Hermes server."""
    transport = httpx.ASGITransport(app=mock_hermes_app)
    return HermesClient(
        base_url="http://test",
        _transport=transport,
    )


@pytest.fixture
def intermediary(hermes_client):
    """Create a TextIntermediary with the mock Hermes client."""
    return TextIntermediary(hermes_client)


# ── Test 1: Refinement removes filler words ─────────────────────────


class TestRefinement:
    """Tests for TextIntermediary._refine filler word removal."""

    def test_removes_um_prefix(self):
        """'um' at the start should be removed."""
        app = create_mock_hermes("test")
        client = HermesClient("http://test", _transport=httpx.ASGITransport(app))
        ti = TextIntermediary(client)
        assert ti._refine("um the docker thing") == "the docker thing"

    def test_removes_so_prefix(self):
        """'so' at the start should be removed."""
        app = create_mock_hermes("test")
        client = HermesClient("http://test", _transport=httpx.ASGITransport(app))
        ti = TextIntermediary(client)
        assert ti._refine("so the docker thing") == "the docker thing"

    def test_removes_like_prefix(self):
        """'like' at the start should be removed."""
        app = create_mock_hermes("test")
        client = HermesClient("http://test", _transport=httpx.ASGITransport(app))
        ti = TextIntermediary(client)
        assert ti._refine("like the docker thing") == "the docker thing"

    def test_removes_um_with_extra_ums(self):
        """Multiple 'um' characters should all be removed."""
        app = create_mock_hermes("test")
        client = HermesClient("http://test", _transport=httpx.ASGITransport(app))
        ti = TextIntermediary(client)
        assert ti._refine("ummm the docker thing") == "the docker thing"

    def test_no_filler_unchanged(self):
        """Text without filler words should be unchanged."""
        app = create_mock_hermes("test")
        client = HermesClient("http://test", _transport=httpx.ASGITransport(app))
        ti = TextIntermediary(client)
        assert ti._refine("check the logs") == "check the logs"

    def test_filler_in_middle_preserved(self):
        """Filler words in the middle should NOT be removed (only prefix)."""
        app = create_mock_hermes("test")
        client = HermesClient("http://test", _transport=httpx.ASGITransport(app))
        ti = TextIntermediary(client)
        assert ti._refine("check um the logs") == "check um the logs"

    def test_case_insensitive(self):
        """Filler removal should be case-insensitive."""
        app = create_mock_hermes("test")
        client = HermesClient("http://test", _transport=httpx.ASGITransport(app))
        ti = TextIntermediary(client)
        assert ti._refine("Um the docker thing") == "the docker thing"
        assert ti._refine("SO the docker thing") == "the docker thing"


# ── Test 2: Chat yields correct IntermediaryEvent objects ───────────


@pytest.mark.asyncio
async def test_text_intermediary_yields_events(intermediary):
    """
    Chat should yield IntermediaryEvent objects with correct speakers in order:
    intermediary → hermes → distilled → system done
    """
    events = []
    async for event in intermediary.chat("um check the docker logs"):
        events.append(event)

    # All items should be IntermediaryEvent
    assert all(isinstance(e, IntermediaryEvent) for e in events)

    # Should have: refined, hermes, distilled, done (at minimum)
    assert len(events) >= 3

    # First event: intermediary (refined user input)
    assert events[0].speaker == Speaker.INTERMEDIARY
    assert events[0].text == "check the docker logs"  # "um" removed
    assert events[0].emotion == Emotion.THINKING

    # Last event: system done
    assert events[-1].speaker == Speaker.SYSTEM
    assert events[-1].text == "done"

    # Middle events: should have hermes and agent_speaking (distilled)
    middle_events = events[1:-1]
    speakers = [e.speaker for e in middle_events]

    # Must contain at least one raw hermes event
    assert Speaker.HERMES in speakers

    # Must contain at least one distilled agent_speaking event
    assert Speaker.AGENT_SPEAKING in speakers

    # Verify chronological order: hermes comes before agent_speaking for each sentence
    hermes_indices = [i for i, e in enumerate(middle_events) if e.speaker == Speaker.HERMES]
    agent_indices = [i for i, e in enumerate(middle_events) if e.speaker == Speaker.AGENT_SPEAKING]
    assert hermes_indices[0] < agent_indices[0]

    # All events should have timestamps
    assert all(e.timestamp > 0 for e in events)


# ── Test 3: Distillation produces shorter output ────────────────────


@pytest.mark.asyncio
async def test_distillation_in_pipeline(intermediary):
    """
    Final distilled output (agent_speaking events) should be shorter than
    or equal to raw Hermes text (hermes events).
    """
    events = []
    async for event in intermediary.chat("check docker"):
        events.append(event)

    # Collect raw hermes text
    hermes_events = [e for e in events if e.speaker == Speaker.HERMES]
    raw_hermes_text = " ".join(e.text for e in hermes_events)

    # Collect distilled text
    distilled_events = [e for e in events if e.speaker == Speaker.AGENT_SPEAKING]
    distilled_text = " ".join(e.text for e in distilled_events)

    # Distilled should be shorter than or equal to raw
    assert len(distilled_text) <= len(raw_hermes_text)

    # Both should be non-empty
    assert len(raw_hermes_text) > 0
    assert len(distilled_text) > 0


@pytest.mark.asyncio
async def test_distillation_preserves_meaning(intermediary):
    """Distilled text should preserve key terms from original."""
    events = []
    async for event in intermediary.chat("check docker"):
        events.append(event)

    distilled_events = [e for e in events if e.speaker == Speaker.AGENT_SPEAKING]
    distilled_text = " ".join(e.text for e in distilled_events)

    # Key terms should be preserved (Docker, permission, denied, error)
    assert "Docker" in distilled_text or "docker" in distilled_text
    assert "permission" in distilled_text or "denied" in distilled_text


# ── Test 4: Barge-in during streaming drops remaining deltas ─────────


@pytest.mark.asyncio
async def test_barge_in_during_stream():
    """
    While streaming, calling steer() to trigger barge-in causes
    should_drop_delta to return True and skips remaining deltas.
    """
    # Long response with slow chunks so we have time to barge in
    app = create_mock_hermes(
        response_text="A" * 200 + ". " + "B" * 200 + ".",
        chunk_size=1,
        chunk_delay=0.01,
    )
    client = HermesClient("http://test", _transport=httpx.ASGITransport(app))
    intermediary = TextIntermediary(client)

    events = []
    hermes_sm = intermediary._barge_in_sm

    # Start streaming in background
    async def run_chat():
        async for event in intermediary.chat("test message"):
            events.append(event)

    task = asyncio.create_task(run_chat())

    # Wait for streaming to start
    await asyncio.sleep(0.05)

    # Simulate user speaking (first turn): LISTENING → SPEAKING
    hermes_sm.on_user_speech("first user input")
    assert hermes_sm.state == BargeInStateMachine.SPEAKING
    assert hermes_sm.should_drop_delta() is False

    # Simulate user barge-in: SPEAKING → STALE
    await intermediary.steer("no wait, check something else")
    assert hermes_sm.state == BargeInStateMachine.STALE
    assert hermes_sm.should_drop_delta() is True

    # Wait for chat to complete
    await task

    # After barge-in, the chat should have dropped many deltas
    # Only early hermes events should have made it through
    hermes_events = [e for e in events if e.speaker == Speaker.HERMES]
    total_hermes_text = "".join(e.text for e in hermes_events)

    # The full response is ~402 chars; we should NOT have all of it
    assert len(total_hermes_text) < 400

    # System done should still be present
    assert events[-1].speaker == Speaker.SYSTEM
    assert events[-1].text == "done"


# ── Test 5: Stale deltas from old context are silently dropped ──────


@pytest.mark.asyncio
async def test_stale_delta_dropped():
    """
    After barge-in, deltas from old context are silently dropped
    (not added to distillation buffer).
    """
    # Create a state machine already in STALE (barge-in occurred)
    sm = BargeInStateMachine()
    sm.on_user_speech("first")  # LISTENING → SPEAKING
    sm.on_user_speech("barge-in!")  # SPEAKING → STALE
    assert sm.should_drop_delta() is True

    buf = DistillationBuffer()

    # Simulate streaming deltas after barge-in
    stale_deltas = []
    for ch in "This is stale text that should be dropped":
        if not sm.should_drop_delta():
            buf.feed(ch)
        else:
            stale_deltas.append(ch)

    # Buffer should NOT contain stale text
    assert "stale" not in buf.buffer
    assert "dropped" not in buf.buffer

    # All deltas should have been dropped
    assert len(stale_deltas) == len("This is stale text that should be dropped")

    # Buffer should be empty (nothing was fed)
    assert buf.buffer == ""

    # After barge-in is handled (INJECT → new response), new deltas pass through
    sm.on_hermes_finish()  # STALE → INJECT
    sm.on_new_response()  # INJECT → SPEAKING
    assert sm.should_drop_delta() is False

    # Now new deltas should pass through
    for ch in "New response text":
        buf.feed(ch)
    assert "New response text" in buf.buffer


# ── Test 6: Full pipeline integration ───────────────────────────────


@pytest.mark.asyncio
async def test_full_pipeline_integration():
    """
    Integration test with mock Hermes — full message → full pipeline → distilled summary.

    Verifies the complete flow:
    1. User sends message with filler words
    2. Message is refined (fillers removed)
    3. Hermes responds with technical output
    4. Output is buffered at sentence boundaries
    5. Each sentence is distilled for speech
    6. Events are emitted in correct order
    7. System signals completion
    """
    # Setup mock Hermes with realistic technical response
    technical_response = (
        "First, let me check the Docker logs. "
        "I can see a permission denied error. "
        "You need to run 'sudo usermod -aG docker $USER'."
    )
    app = create_mock_hermes(
        response_text=technical_response,
        chunk_size=2,
        chunk_delay=0.001,
    )
    client = HermesClient("http://test", _transport=httpx.ASGITransport(app))
    intermediary = TextIntermediary(client, session_id="test-session")

    # Run the full pipeline (single filler word — refinement only removes one prefix)
    events = []
    async for event in intermediary.chat("um fix my docker permissions"):
        events.append(event)

    # ── Verify event structure ──

    # All events should be IntermediaryEvent instances
    assert all(isinstance(e, IntermediaryEvent) for e in events)

    # Should have at least 4 events: refined, 1 hermes, 1 distilled, done
    assert len(events) >= 4

    # ── Verify refinement (event 0) ──
    refined_event = events[0]
    assert refined_event.speaker == Speaker.INTERMEDIARY
    assert refined_event.text == "fix my docker permissions"
    assert refined_event.emotion == Emotion.THINKING
    assert refined_event.timestamp > 0

    # ── Verify system done (last event) ──
    done_event = events[-1]
    assert done_event.speaker == Speaker.SYSTEM
    assert done_event.text == "done"
    assert done_event.timestamp > 0

    # ── Verify Hermes events (middle section) ──
    hermes_events = [e for e in events if e.speaker == Speaker.HERMES]
    assert len(hermes_events) >= 1

    # Reconstruct raw Hermes text
    raw_hermes_text = " ".join(e.text for e in hermes_events)
    assert "Docker" in raw_hermes_text or "docker" in raw_hermes_text
    assert "permission" in raw_hermes_text

    # ── Verify distilled events ──
    distilled_events = [e for e in events if e.speaker == Speaker.AGENT_SPEAKING]
    assert len(distilled_events) >= 1

    # Each distilled event should be <= 2 sentences (distillation rule)
    for de in distilled_events:
        assert de.emotion == Emotion.NEUTRAL
        # Count sentences (rough: split on .!?)
        import re
        sentences = re.split(r'(?<=[.!?])\s+', de.text.strip())
        assert len(sentences) <= 2

    # All distilled text should be shorter than raw
    distilled_text = " ".join(e.text for e in distilled_events)
    assert len(distilled_text) <= len(raw_hermes_text)

    # ── Verify chronological order ──
    for i in range(len(events) - 1):
        assert events[i].timestamp <= events[i + 1].timestamp

    # ── Verify speaker ordering: hermes before distilled for each sentence ──
    middle = events[1:-1]  # exclude refined and done
    hermes_indices = [i for i, e in enumerate(middle) if e.speaker == Speaker.HERMES]
    agent_indices = [i for i, e in enumerate(middle) if e.speaker == Speaker.AGENT_SPEAKING]
    assert hermes_indices[0] < agent_indices[0]
