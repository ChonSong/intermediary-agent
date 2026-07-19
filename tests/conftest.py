"""Test fixtures for intermediary agent tests."""

import asyncio
import pytest
import httpx
from typing import Optional

from intermediary.hermes_client import HermesClient
from intermediary.mock_hermes import create_mock_hermes


@pytest.fixture
def mock_hermes():
    """Mock Hermes server with default response."""
    app = create_mock_hermes(
        response_text="First, let me check the Docker logs.",
        chunk_size=1,
        chunk_delay=0.001,
    )
    return app


@pytest.fixture
def client(mock_hermes):
    """HermesClient pointing to the mock server."""
    transport = httpx.ASGITransport(app=mock_hermes)
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
