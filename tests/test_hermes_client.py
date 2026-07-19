"""
Test HermesClient against the mock Hermes server.
"""

import pytest
import httpx

from intermediary.hermes_client import HermesClient
from intermediary.mock_hermes import create_mock_hermes


@pytest.fixture
def client():
    """Create a HermesClient with a mock server."""
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


@pytest.fixture
def client_factory():
    """Factory for HermesClient with custom response."""
    def _make(response_text="Hello world.", chunk_size=1, chunk_delay=0.001):
        app = create_mock_hermes(
            response_text=response_text,
            chunk_size=chunk_size,
            chunk_delay=chunk_delay,
        )
        transport = httpx.ASGITransport(app=app)
        return HermesClient(
            base_url="http://test",
            _transport=transport,
        )
    return _make


@pytest.fixture
async def client_with_session(client):
    """Create a client and a session for testing."""
    session_id = await client.create_session()
    return client, session_id


@pytest.mark.asyncio
async def test_create_session(client):
    """create_session returns a valid session ID."""
    session_id = await client.create_session()
    assert session_id.startswith("ses-")


@pytest.mark.asyncio
async def test_start_chat(client_with_session):
    """start_chat returns a valid stream_id."""
    client, session_id = client_with_session
    stream_id = await client.start_chat("test message", session_id)
    assert stream_id.startswith("stream-")


@pytest.mark.asyncio
async def test_stream_chat(client_with_session):
    """stream_chat returns all deltas from Hermes stream."""
    client, session_id = client_with_session
    stream_id = await client.start_chat("test", session_id)
    deltas = []
    async for delta in client.stream_chat(stream_id):
        deltas.append(delta)
    full_text = "".join(deltas)
    assert full_text == "First, let me check the Docker logs."


@pytest.mark.asyncio
async def test_steer_accepted(client_with_session):
    """steer is accepted while stream is active."""
    client, session_id = client_with_session
    stream_id = await client.start_chat("test", session_id)
    result = await client.steer(session_id, "no the other error")
    assert result["accepted"] is True


@pytest.mark.asyncio
async def test_stream_in_chunks(client_factory):
    """Test that streaming rebuilds the full text from chunks."""
    """Test that chunks rebuild the full text."""
    c = client_factory(response_text="Hello world!", chunk_size=2, chunk_delay=0.001)
    session_id = await c.create_session()
    stream_id = await c.start_chat("test", session_id)
    deltas = []
    async for delta in c.stream_chat(stream_id):
        deltas.append(delta)
    assert all(len(d) <= 2 for d in deltas)
    assert "".join(deltas) == "Hello world!"


@pytest.mark.asyncio
async def test_refinement_preprocessing():
    """Test basic refinement of raw input."""
    from intermediary.text_intermediary import TextIntermediary
    app = create_mock_hermes(response_text="Test response.")
    transport = httpx.ASGITransport(app=app)
    client = HermesClient(base_url="http://test", _transport=transport)
    intermediary = TextIntermediary(client)
    
    # Test filler removal
    refined = intermediary._refine("um, hello world")
    assert refined == "hello world"
    
    refined = intermediary._refine("so like test")
    assert refined == "test"
    
    refined = intermediary._refine("ummm test")
    assert refined == "test"
    
    # No filler - unchanged
    refined = intermediary._refine("hello world")
    assert refined == "hello world"
