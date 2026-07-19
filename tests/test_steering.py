import asyncio
import time
import pytest
import httpx

from intermediary.steering import BargeInStateMachine
from intermediary.distillation import DistillationBuffer, distill
from intermediary.mock_hermes import create_mock_hermes
from intermediary.hermes_client import HermesClient


# ── Unit tests ──────────────────────────────────────────────────────


def test_initial_state():
    assert BargeInStateMachine().state == "LISTENING"


def test_normal_turn_cycle():
    sm = BargeInStateMachine()
    sm.on_user_speech("hello")
    assert sm.state == "SPEAKING"
    sm.on_hermes_finish()
    assert sm.state == "LISTENING"


def test_barge_in_steer_immediate():
    sm = BargeInStateMachine()
    sm.on_user_speech("hello")
    t0 = time.perf_counter()
    sm.on_user_speech("no wait")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert sm.state == "STALE"
    assert sm.steer_active is True
    assert elapsed_ms < 1.0  # steer is posted instantly


def test_stale_to_inject_to_speaking():
    sm = BargeInStateMachine()
    sm.on_user_speech("hi")
    sm.on_user_speech("stop")
    assert sm.state == "STALE"
    sm.on_hermes_finish()
    assert sm.state == "INJECT"
    sm.on_new_response()
    assert sm.state == "SPEAKING"
    assert sm.steer_active is False


def test_delta_drop_scope():
    sm = BargeInStateMachine()
    sm.on_user_speech("hi")
    assert sm.should_drop_delta() is False
    sm.on_user_speech("wait")
    assert sm.should_drop_delta() is True
    sm.on_hermes_finish()
    sm.on_new_response()
    assert sm.should_drop_delta() is False


def test_double_barge():
    sm = BargeInStateMachine()
    sm.on_user_speech("hi")
    sm.on_user_speech("wait")
    sm.on_user_speech("no the OTHER")
    assert sm.pending_steer == "no the OTHER"


# ── Integration tests with mock Hermes ──────────────────────────────


@pytest.mark.asyncio
async def test_normal_turn():
    app = create_mock_hermes("First, let me check.", chunk_delay=0.001)
    c = HermesClient("http://test", _transport=httpx.ASGITransport(app))
    sid = await c.create_session()
    stream_id = await c.start_chat("test", sid)
    deltas = [d async for d in c.stream_chat(stream_id)]
    assert "".join(deltas) == "First, let me check."


@pytest.mark.asyncio
async def test_steer_accepted_while_stream_active():
    """Steer POST returns accepted because stream is still active."""
    app = create_mock_hermes("A" * 200, chunk_size=4, chunk_delay=0.05)
    c = HermesClient("http://test", _transport=httpx.ASGITransport(app))
    sid = await c.create_session()
    stream_id = await c.start_chat("test", sid)
    # Don't stream — just verify steer is accepted
    await asyncio.sleep(0.1)
    result = await c.steer(sid, "no wait")
    assert result["accepted"] is True


@pytest.mark.asyncio
async def test_stale_deltas_dropped():
    """After barge-in, stale deltas from the old response are dropped."""
    buf = DistillationBuffer()
    sm = BargeInStateMachine()

    for ch in "First, let me check":
        if not sm.should_drop_delta():
            buf.feed(ch)
    assert "First, let me check" in buf.buffer

    # Barge-in
    sm.on_user_speech("hi")
    sm.on_user_speech("no wait")
    assert sm.should_drop_delta()

    # Stale delta should be dropped
    for ch in "stale text":
        if not sm.should_drop_delta():
            buf.feed(ch)
    assert "stale" not in buf.buffer


@pytest.mark.asyncio
async def test_distill_with_barge_in():
    """Full pipeline simulation: SSE → distill with barge-in handling."""
    buf = DistillationBuffer()
    sm = BargeInStateMachine()
    sm.on_user_speech("hi")  # start turn

    output = []
    for ch in "First sentence. Second sentence.":
        if sm.should_drop_delta():
            continue
        result = buf.feed(ch)
        if result:
            output.append(await distill(result))

    assert len(output) >= 1

    sm.on_user_speech("wait")
    assert sm.should_drop_delta()

    for ch in "dropped text":
        if sm.should_drop_delta():
            continue
        buf.feed(ch)
    assert "dropped" not in buf.buffer
