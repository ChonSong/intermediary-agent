"""HTTP client for Hermes WebUI API.

Supports:
- Session creation
- Chat (POST /api/chat/start → stream_id, GET /api/chat/stream → SSE deltas)
- Steering (POST /api/chat/steer)
"""

import json
import httpx
from typing import AsyncIterable, Optional


class HermesClient:
    """HTTP client for Hermes WebUI API."""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None, _transport=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, read=None),
            headers=self._auth_headers(),
            transport=_transport,
        )
    
    def _auth_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def close(self):
        await self._client.aclose()
    
    async def create_session(self) -> str:
        """Create a new Hermes session. Returns session_id."""
        resp = await self._client.post(f"{self.base_url}/api/sessions")
        resp.raise_for_status()
        data = resp.json()
        return data["session_id"]
    
    async def start_chat(self, message: str, session_id: str) -> str:
        """Start a Hermes chat run. Returns stream_id."""
        resp = await self._client.post(
            f"{self.base_url}/api/chat/start",
            json={
                "session_id": session_id,
                "message": message,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["stream_id"]
    
    async def stream_chat(self, stream_id: str) -> AsyncIterable[str]:
        """
        Stream Hermes response via SSE.
        
        Yields text deltas (1-4 chars each).
        Filters out non-delta events (tool_use, thinking, done).
        """
        url = f"{self.base_url}/api/chat/stream"
        async with self._client.stream("GET", url, params={"stream_id": stream_id}) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if data.get("type") == "delta":
                            yield data["content"]
                    except json.JSONDecodeError:
                        continue
    
    async def steer(self, session_id: str, text: str) -> dict:
        """Inject steer into active agent loop (non-interrupting).
        
        Must be called WHILE the agent is still running (SSE stream active).
        If the run is complete, returns {"accepted": false, "fallback": "stream_dead"}.
        """
        resp = await self._client.post(
            f"{self.base_url}/api/chat/steer",
            json={
                "session_id": session_id,
                "text": text,
            },
        )
        resp.raise_for_status()
        return resp.json()
