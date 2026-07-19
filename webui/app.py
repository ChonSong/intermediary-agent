"""Transcript UI — FastAPI app for displaying intermediary conversation.

User sees:
- LiveKit transcription events forwarded via WebSocket
- Color-coded transcript: user=blue, intermediary=green, hermes=gray
- Connection status indicator
- Barge-in / steer events

Run: python -m uvicorn webui.app:app --host 0.0.0.0 --port 8080
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

app = FastAPI(title="Intermediary Transcript")

# Mount static files
app.mount("/static", StaticFiles(directory="webui/static"), name="static")

# Store active WebSocket connections
active_connections: list[WebSocket] = []

# Global event queue (in production use Redis or LiveKit webhooks)
event_queue: asyncio.Queue = asyncio.Queue()


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Intermediary Transcript</title>
        <link rel="stylesheet" href="/static/styles.css">
    </head>
    <body>
        <header>
            <h1>Intermediary Agent</h1>
            <div id="status" class="status disconnected">Disconnected</div>
        </header>

        <main>
            <div id="transcript" class="transcript"></div>
        </main>

        <script src="/static/transcript.js"></script>
    </body>
    </html>
    """


@app.websocket("/ws/transcript")
async def transcript_ws(websocket: WebSocket):
    """WebSocket endpoint for receiving transcription events.

    Events come from the intermediary agent (forwarded LiveKit transcription events).
    """
    await websocket.accept()
    active_connections.append(websocket)
    logger.info("Client connected")

    try:
        while True:
            # Wait for events from the queue
            event = await event_queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info("Client disconnected")


@app.post("/api/events/transcript")
async def receive_transcript_event(event: dict):
    """HTTP endpoint for intermediary agent to push transcription events.

    In production, the intermediary agent calls this endpoint via HTTP POST
    whenever a transcription event fires.
    """
    await event_queue.put(event)
    return {"ok": True}


async def broadcast_event(event: dict):
    """Broadcast an event to all connected WebSocket clients."""
    for conn in active_connections:
        try:
            await conn.send_json(event)
        except Exception:
            pass
