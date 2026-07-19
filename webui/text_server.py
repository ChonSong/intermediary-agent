"""Text MVP — FastAPI server for text-only intermediary."""

import asyncio
import json
import logging
import os
import uuid
from typing import AsyncIterable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import httpx

from intermediary.text_intermediary import TextIntermediary
from intermediary.hermes_client import HermesClient
from intermediary.events import IntermediaryEvent
from intermediary.mock_hermes import create_mock_hermes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Intermediary Text MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="webui/static"), name="static")

# In-memory store for active intermediaries
active_chats: dict[str, tuple[TextIntermediary, str]] = {}

HERMES_URL = os.environ.get("HERMES_URL", "http://127.0.0.1:9119")
USE_MOCK = os.environ.get("HERMES_MOCK", "true").lower() == "true"


def get_hermes_client() -> HermesClient:
    """Get HermesClient (real or mock)."""
    if USE_MOCK:
        return _create_mock_client()
    return HermesClient(HERMES_URL)


def _create_mock_client() -> HermesClient:
    """Create a HermesClient backed by mock Hermes server."""
    mock_app = create_mock_hermes(
        response_text=(
            "First, let me check the Docker logs. "
            "I can see a permission denied error on the Docker socket. "
            "Run this command to fix it: sudo usermod -aG docker $USER"
        ),
        chunk_size=1,
        chunk_delay=0.01,
    )
    transport = httpx.ASGITransport(app=mock_app)
    return HermesClient("http://test", _transport=transport)


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("webui/templates/mvp.html", "r") as f:
        return f.read()


@app.get("/api/health")
async def health():
    return {"ok": True, "mock": USE_MOCK}


@app.post("/api/chat")
async def start_chat(request: Request):
    """Start a new chat. Returns stream_id for SSE streaming."""
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    hermes_client = get_hermes_client()
    intermediary = TextIntermediary(hermes_client)

    stream_id = f"chat-{uuid.uuid4().hex[:8]}"
    active_chats[stream_id] = (intermediary, message)

    return {
        "stream_id": stream_id,
        "refined": intermediary._refine(message),
    }


@app.get("/api/chat/stream")
async def chat_stream(stream_id: str):
    """SSE stream of IntermediaryEvents."""
    if stream_id not in active_chats:
        raise HTTPException(status_code=404, detail="stream not found")

    intermediary, message = active_chats[stream_id]

    async def generate() -> AsyncIterable[str]:
        try:
            async for event in intermediary.chat(message):
                data = event.to_dict()
                yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Stream error: {e}")
            error_event = IntermediaryEvent(
                speaker="system",
                text=f"Error: {e}",
                timestamp=__import__("time").time(),
            )
            yield f"data: {json.dumps(error_event.to_dict())}\n\n"
        finally:
            if stream_id in active_chats:
                active_chats.pop(stream_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/chat/steer")
async def steer(request: Request):
    """Inject steer into active chat."""
    body = await request.json()
    stream_id = body.get("stream_id")
    text = body.get("text", "").strip()

    if not stream_id or stream_id not in active_chats:
        raise HTTPException(status_code=404, detail="stream not found")

    intermediary, _ = active_chats[stream_id]
    result = await intermediary.steer(text)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webui.text_server:app", host="0.0.0.0", port=8080, reload=True)
