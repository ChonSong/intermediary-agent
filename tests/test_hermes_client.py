"""
Test HermesClient against the mock Hermes server.
"""

import pytest
import httpx

from intermediary.hermes_client import HermesClient
from intermediary.mock_hermes import create_mock_hermes


@pytest.fixture
def client():
    app = create_mock_hermes(
        response_text="First, let me check the Docker logs.",
        chunk_size=1,
        chunk_delay=0.001,
    )
    transport = httpx.ASGITransport(app=app)
    return HermesClient(
        base_url="http://test",
        _transport=transport,
    )


@pytest.mark.asyncio
async def test_create_session(client):
    session_id = await client.create_session()
    assert session_id.startswith("ses-")


@pytest.mark.asyncio
async def test_start_chat(client):
    stream_id = await client.start_chat("test message", "ses-123")
    assert stream_id.startswith("stream-")


@pytest.mark.asyncio
async def test_stream_chat(client):
    stream_id = await client.start_chat("test", "ses-123")
    deltas = []
    async for delta in client.stream_chat(stream_id):
        deltas.append(delta)
    full_text = "".join(deltas)
    assert full_text == "First, let me check the Docker logs."


@pytest.mark.asyncio
async def test_steer_accepted(client):
    # Start a chat to create an active stream
    stream_id = await client.start_chat("test", "ses-123")
    # Steer while stream is active
    result = await client.steer("ses-123", "no the other error")
    assert result["accepted"] is True


@pytest.mark.asyncio
async def test_stream_in_chunks(client):
    """Test that streaming rebuilds the full text from chunks."""
    app = create_mock_hermes(
        response_text="Hello world!",
        chunk_size=2,  # 2-char deltas
        chunk_delay=0.001,
    )
    transport = httpx.ASGITransport(app=app)
    c = HermesClient(base_url="http://test", _transport=transport)
    
    stream_id = await c.start_chat("test", "ses-123")
    deltas = []
    async for delta in c.stream_chat(stream_id):
        deltas.append(delta)
    
    # Each delta should be 2 chars (except last)
    assert all(len(d) <= 2 for d in deltas)
    assert "".join(deltas) == "Hello world!"
