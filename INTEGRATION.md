# Intermediary Agent — Integration Points

> File paths, API endpoints, and configuration for integrating with Hermes and external services.

---

## Architecture Summary

The intermediary connects to Hermes via the existing **WebUI HTTP API**. Audio runs through browser WebRTC (getUserMedia + WebSocket). No LiveKit needed.

```
Browser (mic/speakers) ⟷ WebSocket ⟷ Voice Server ⟷ Hermes API
     getUserMedia()          PCM frames       HTTP/SSE
     WebRTC AEC
```

---

## Hermes WebUI Integration

### Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sessions` | POST | Create new Hermes session |
| `/api/chat/start` | POST | `{session_id, message}` → `{stream_id}` |
| `/api/chat/stream` | GET | `?stream_id=...` → SSE deltas |
| `/api/chat/steer` | POST | `{session_id, text}` → `{accepted: bool}` |

### Steer Mechanism

```python
# streaming.py _handle_chat_steer():
cached = SESSION_AGENT_CACHE.get(session_id)
agent = cached[0]
accepted = agent.steer(text)
# → Text stashed in _pending_steer
# → Applied at next tool-result boundary with "User guidance:" marker
```

### SSE Stream Format

```
data: {"type": "delta", "content": "First, let me check"}
data: {"type": "tool_use", "tool": "read_file", "args": {"path": "/var/log/syslog"}}
data: {"type": "thinking", "content": "Let me think..."}
data: {"type": "error", "message": "Something went wrong"}
data: {"type": "done"}
```

### Hermes Response Types

| Type | What to Do | Distill? |
|------|-----------|----------|
| `delta` | Pass to distillation → TTS → transcript UI | Yes |
| `tool_use` | Show "Using tool: X" in transcript | No |
| `thinking` | Suppress from TTS | No |
| `error` | Speak error message | Yes |
| `done` | Check for pending steer | No |

### Hermes API Auth

```python
# If Hermes has auth enabled:
headers = {"Authorization": f"Bearer {api_key}"}

# If no auth (default for local):
headers = {}
```

---

## Hermes Agent (Gateway) — Future

For future tighter integration with hermes-agent (not WebUI):

| File | Change |
|------|--------|
| `hermes_cli/plugins.py` | Add `intermediary_*` hooks to `VALID_HOOKS` |
| `hermes_cli/plugins.py` | Add `ctx.steer_agent(session_id, text)` method |
| `hermes_cli/config.py` | Add `intermediary:` config section |
| `gateway/platforms/discord.py` | Wire intermediary surface |

---

## Local Voice Services (Path C)

| Service | Library | API | Port |
|---------|---------|-----|------|
| STT | faster-whisper | OpenAI-compat / HTTP | 8002 |
| LLM | Ollama | OpenAI-compat / HTTP | 11434 |
| TTS | Kokoro | HTTP | 8880 |
| VAD | silero-vad | In-process | — |
| Audio Transport | uvicorn | WebSocket | 8000 |

### Ollama Configuration

```bash
# Install models:
ollama pull qwen2.5:7b

# API endpoint:
OLLAMA_URL=http://localhost:11434

# Usage (via intermediary):
import openai
client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
client.chat.completions.create(model="qwen2.5:7b", messages=[...])
```

### faster-whisper Configuration

```bash
# Install:
pip install faster-whisper

# Models:
- base (74M, CPU real-time)
- medium (800M, faster)
- large-v3 (1.5B, best quality)
```

### Kokoro Configuration

```bash
# Install:
pip install kokoro-onnx soundfile

# Usage:
from kokoro_onnx import Kokoro
kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")
samples, sample_rate = kkokoro.create(text, voice="af", lang="en-us")
```

### silero-vad Configuration

```python
import torch
model, utils = torch.hub.load(repo_or_dir="snakers4/silero-vad", model="silero_vad")
(get_speech_timestamps, _, read_audio, _, _) = utils

speech_timestamps = get_speech_timestamps(audio, model, sampling_rate=16000)
# Returns list of {"start": 0, "end": 15680} dicts
```

---

## Configuration Reference

```yaml
# config.yaml

intermediary:
  enabled: true
  hermes_url: "http://localhost:3000"
  hermes_api_key: null
  features:
    refine: true
    distill: true
    steer: true

audio:
  backend: websocket    # websocket (Path C)
  sample_rate: 16000
  frame_duration_ms: 20
  vad_sensitivity: 0.5

voice_service:
  stt:
    provider: faster-whisper
    model: base
    url: null   # use local if unset
  llm:
    provider: ollama
    model: qwen2.5:7b
    url: http://localhost:11434
  tts:
    provider: kokoro
    url: http://localhost:8880

frontend:
  host: "0.0.0.0"
  port: 8080
```

---

## File Paths in hermes-agent (For Future Integration)

| File | Line | Function |
|------|------|----------|
| `api/routes.py` | ~21240 | `_handle_chat_start` |
| `api/routes.py` | ~12895 | `_handle_session_sse_stream` |
| `api/streaming.py` | ~10296 | `_handle_chat_steer` |

No changes required for text-only MVP. Future voice phases may add plugin hooks.

---

## Existing Extension System (hermes-webui)

Find extension hooks at:
- `api/extensions.py` — `registerHermesTtsEngine({id, label, synthesize})`
- `static/boot.js` — STT + MediaRecorder voice paths
- `static/panels.js` — Voice preferences

A future WebUI extension would:
1. Load intermediary voice hooks
2. Forward STT text to intermediary
3. Subscribe to intermediary SSE stream
4. Display color-coded transcript in WebUI
