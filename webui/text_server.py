"""Text MVP — FastAPI server for text-only intermediary."""

import asyncio
import json
import logging
import os
import uuid
from typing import AsyncIterable, Optional

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

# In-memory store: stream_id -> (intermediary, message, real_stream_id)
active_chats: dict[str, tuple] = {}

HERMES_URL = os.environ.get("HERMES_URL", "http://127.0.0.1:8788")
USE_MOCK = os.environ.get("HERMES_MOCK", "true").lower() == "true"
HERMES_PASSWORD = os.environ.get("HERMES_PASSWORD", "Cheong02")


def get_hermes_client(cookie: Optional[str] = None) -> HermesClient:
    """Get HermesClient (real or mock)."""
    if USE_MOCK:
        return _create_mock_client()
    return HermesClient(HERMES_URL, cookie=cookie)


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


@app.post("/api/session")
async def create_session(request: Request):
    """Create a real Hermes session. Returns session_id and cookie."""
    if USE_MOCK:
        return {"session_id": "mock-session", "cookie": ""}
    
    async with httpx.AsyncClient() as client:
        login_resp = await client.post(
            f"{HERMES_URL}/api/auth/login",
            json={"password": HERMES_PASSWORD},
        )
        login_resp.raise_for_status()
        cookie = login_resp.cookies.get("hermes_session", "")
        
        resp = await client.post(
            f"{HERMES_URL}/api/session/new",
            cookies={"hermes_session": cookie},
        )
        resp.raise_for_status()
        data = resp.json()
        
        return {
            "session_id": data["session"]["session_id"],
            "cookie": cookie,
        }


@app.post("/api/chat")
async def start_chat(request: Request):
    """Start a new chat. Returns stream_id for SSE streaming."""
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    if USE_MOCK:
        hermes_client = _create_mock_client()
        intermediary = TextIntermediary(hermes_client)
        stream_id = f"chat-{uuid.uuid4().hex[:8]}"
        active_chats[stream_id] = (intermediary, message, None)
        return {
            "stream_id": stream_id,
            "refined": intermediary._refine(message),
        }
    else:
        # Real Hermes with session + cookie
        session_id = body.get("session_id")
        cookie = body.get("cookie")
        
        if not session_id or not cookie:
            return {"error": "session_id and cookie required. Call /api/session first."}
        
        hermes_client = HermesClient(HERMES_URL, cookie=cookie)
        
        # Create intermediary with the real session
        intermediary = TextIntermediary(hermes_client, session_id=session_id)
        refined = intermediary._refine(message)
        
        # Start real Hermes chat with refined message (this returns immediately)
        real_stream_id = await hermes_client.start_chat(refined, session_id)
        
        stream_id = f"chat-{uuid.uuid4().hex[:8]}"
        active_chats[stream_id] = (intermediary, message, real_stream_id)
        
        return {
            "stream_id": stream_id,
            "real_stream_id": real_stream_id,
            "refined": refined,
        }


@app.get("/api/chat/stream")
async def chat_stream(stream_id: str):
    """SSE stream of IntermediaryEvents."""
    if stream_id not in active_chats:
        raise HTTPException(status_code=404, detail="stream not found")

    intermediary, message, real_stream_id = active_chats[stream_id]

    async def generate() -> AsyncIterable[str]:
        try:
            # Pass the real_stream_id so intermediary doesn't start a new chat
            async for event in intermediary.chat(message, stream_id=real_stream_id):
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

    intermediary, _, _ = active_chats[stream_id]
    result = await intermediary.steer(text)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webui.text_server:app", host="0.0.0.0", port=8080, reload=True)
