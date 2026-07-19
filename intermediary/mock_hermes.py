"""
Mock Hermes server for testing.

Mimics the EXACT real Hermes WebUI API format:
- POST /api/session/new → {session: {session_id, title, workspace}}
- POST /api/chat/start → {stream_id}
- GET /api/chat/stream?stream_id=... → SSE stream with 'event: reasoning' lines
- POST /api/chat/steer → {accepted: bool}
"""

import asyncio
import json
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse


def create_mock_hermes(
    response_text: str = "First, let me check the Docker logs. I can see a permission denied error.",
    chunk_size: int = 1,
    chunk_delay: float = 0.01,
    steer_accepted: bool = True,
) -> FastAPI:
    """Create a mock Hermes WebUI server.
    
    Args:
        response_text: The full response text to stream as SSE deltas
        chunk_size: Number of characters per delta (1-4 mimics real Hermes)
        chunk_delay: Delay between chunks in seconds
        steer_accepted: Whether to accept steer requests
    """
    app = FastAPI()
    
    active_streams: dict[str, dict] = {}
    active_sessions: dict[str, dict] = {}
    
    @app.post("/api/session/new")
    async def create_session():
        session_id = f"ses-{uuid.uuid4().hex[:8]}"
        active_sessions[session_id] = {"session_id": session_id}
        return {"session": {"session_id": session_id, "title": "Untitled", "workspace": "/home/sc/workspace"}}
    
    @app.post("/api/chat/start")
    async def chat_start(body: dict):
        session_id = body.get("session_id", "")
        message = body.get("message", "")
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        stream_id = f"stream-{uuid.uuid4().hex[:8]}"
        active_streams[stream_id] = {
            "session_id": session_id,
            "message": message,
            "steered": False,
            "steer_text": None,
        }
        return {"stream_id": stream_id}
    
    @app.get("/api/chat/stream")
    async def chat_stream(stream_id: str):
        if stream_id not in active_streams:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        stream_info = active_streams[stream_id]
        
        async def generate():
            text = response_text
            if stream_info["steered"] and stream_info["steer_text"]:
                text = f"Ah, you meant {stream_info['steer_text']}. Let me check that instead."
            
            # Real Hermes SSE format: "id: stream_id:N\nevent: reasoning\ndata: {"text": "..."}"
            n = 0
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                n += 1
                yield f"id: {stream_id}:{n}\n"
                yield f"event: reasoning\ndata: {json.dumps({'text': chunk})}\n\n"
                await asyncio.sleep(chunk_delay)
            
            # Done event
            n += 1
            yield f"id: {stream_id}:{n}\n"
            yield f"event: done\ndata: {{}}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )
    
    @app.post("/api/chat/steer")
    async def chat_steer(body: dict):
        session_id = body.get("session_id", "")
        text = body.get("text", "")
        
        for stream_id, info in active_streams.items():
            if info["session_id"] == session_id:
                info["steered"] = True
                info["steer_text"] = text
                return {"accepted": steer_accepted}
        
        return {"accepted": False, "fallback": "not_running"}
    
    return app
