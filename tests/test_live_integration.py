"""
Phase 1.6b — Live integration test against real Hermes WebUI.

The real Hermes WebUI (port 9119) requires authentication.
This test verifies:
- HermesClient can connect to the real server
- SSE streaming works against the real /api/chat endpoint
- Steer injection works against the real /api/chat/steer endpoint

This is a manual/CI test that requires:
1. Hermes WebUI running on port 9119 (or env HERMES_URL)
2. Valid auth token from Hermes dashboard session

Run with: pytest tests/test_live_integration.py -v -s
"""

import asyncio
import os
import httpx
import pytest

from intermediary.hermes_client import HermesClient


HERMES_URL = os.environ.get("HERMES_URL", "http://127.0.0.1:9119")
AUTH_TOKEN = os.environ.get("HERMES_AUTH_TOKEN", "")


@pytest.fixture
def hermes_client():
    headers = {}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    return HermesClient(HERMES_URL, headers=headers)


@pytest.mark.skipif(not AUTH_TOKEN, reason="HERMES_AUTH_TOKEN not set")
@pytest.mark.asyncio
async def test_real_hermes_connection(hermes_client):
    """Verify we can connect to real Hermes WebUI."""
    try:
        session_id = await hermes_client.create_session()
        assert session_id is not None
        assert len(session_id) > 0
        print(f"Created session: {session_id}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            pytest.skip("Unauthorized — need valid auth token")
        raise


@pytest.mark.skipif(not AUTH_TOKEN, reason="HERMES_AUTH_TOKEN not set")
@pytest.mark.asyncio
async def test_real_hermes_chat_stream(hermes_client):
    """Verify SSE streaming against real Hermes."""
    session_id = await hermes_client.create_session()
    stream_id = await hermes_client.start_chat("Hello, Hermes!", session_id)

    deltas = []
    async for delta in hermes_client.stream_chat(stream_id):
        deltas.append(delta)

    full_text = "".join(deltas)
    assert len(full_text) > 0
    print(f"Response: {full_text!r}")


@pytest.mark.skipif(not AUTH_TOKEN, reason="HERMES_AUTH_TOKEN not set")
@pytest.mark.asyncio
async def test_real_hermes_steer(hermes_client):
    """Verify steer injection against real Hermes."""
    session_id = await hermes_client.create_session()
    stream_id = await hermes_client.start_chat("Tell me a long story", session_id)

    async def consume():
        deltas = []
        async for delta in hermes_client.stream_chat(stream_id):
            deltas.append(delta)
        return deltas

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.5)

    result = await hermes_client.steer(session_id, "stop")
    assert result["accepted"] is True

    deltas = await asyncio.wait_for(task, timeout=30)
    assert len(deltas) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
