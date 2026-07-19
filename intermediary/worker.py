"""LiveKit worker entry point for the intermediary voice agent.

Run with:
    python -m intermediary.worker

Requires:
    LiveKit server running (livekit-server --dev)
    OPENAI_API_KEY env var
    CARTESIA_API_KEY env var (or configured TTS provider)
    DEEPGRAM_API_KEY env var (or configured STT provider)
"""

import asyncio
import logging
import os
import sys

from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.voice import AgentSession
from livekit.plugins import openai, deepgram, cartesia

from .voice_agent import VoiceIntermediaryAgent
from .config import IntermediaryConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def entrypoint(ctx: JobContext):
    """LiveKit job entry point."""
    config = IntermediaryConfig()
    agent = VoiceIntermediaryAgent(config)

    # Create LiveKit session with STT/LLM/TTS
    session = AgentSession(
        stt=deepgram.STT(api_key=os.environ.get("DEEPGRAM_API_KEY")),
        llm=openai.LLM(
            model="gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY"),
        ),
        tts=cartesia.TTS(api_key=os.environ.get("CARTESIA_API_KEY")),
    )

    agent.session = session

    # Add Hermes query tool
    tools = agent._get_tools()
    session.llm.tools.extend(tools)

    # Start session (connects to room from LiveKit server)
    await session.start(room=ctx.room)

    logger.info(f"Voice agent joined room: {ctx.room.name}")

    # Keep alive
    while True:
        await asyncio.sleep(1)


def main():
    """Run the LiveKit worker."""
    required = ["OPENAI_API_KEY"]
    missing = [var for var in required if not os.environ.get(var)]
    if missing:
        missing_str = ", ".join(missing)
        logger.error(f"Missing required env vars: {missing_str}")
        sys.exit(1)

    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
