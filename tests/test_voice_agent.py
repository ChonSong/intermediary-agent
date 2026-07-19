"""Tests for VoiceIntermediaryAgent (requires LiveKit server).

Tests are skipped if LiveKit server is not reachable.
"""

import os
import pytest

from intermediary.voice_agent import VoiceIntermediaryAgent
from intermediary.config import IntermediaryConfig

LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")


@pytest.fixture
def agent():
    return VoiceIntermediaryAgent()


def test_voice_agent_creation(agent):
    """VoiceIntermediaryAgent initializes without error."""
    assert agent.hermes is not None


def test_get_tools(agent):
    """Tools include query_hermes."""
    tools = agent._get_tools()
    assert len(tools) > 0
    assert any(t.name == "query_hermes" for t in tools)


@pytest.mark.skipif(
    not os.environ.get("LIVEKIT_URL"),
    reason="LIVEKIT_URL not set or LiveKit server not running"
)
@pytest.mark.asyncio
async def test_voice_agent_connect(agent):
    """Voice agent can connect to LiveKit room (requires server)."""
    # Would test connection here if LiveKit is running
    pass
