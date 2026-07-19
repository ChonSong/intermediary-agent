# Intermediary Agent — Complete Implementation Plan

> Self-hosted voice intermediary. Zero third-party API dependencies. All models run locally. Hermes runs as a separate API.

---

## Architecture

```
Browser (mic/speakers) ⟷ WebSocket ⟷ Voice Server (Python) ⟷ Hermes API
     getUserMedia()         PCM frames        STT → LLM → TTS
     WebRTC AEC                             (all local)
```

All models run locally:
- **STT**: faster-whisper (speech → text)
- **LLM**: Ollama qwen2.5:7b (intermediary: refine + distill + steer)
- **TTS**: Kokoro-82m (text → audio)
- **VAD**: silero-vad (speech/silence detection)
- **Hermes**: Existing API (reasoning)

## Why Not LiveKit?

LiveKit requires commercial providers (Deepgram/OpenAI/Cartesia) for speech components. Local models provide equivalent quality with full privacy and zero ongoing cost.

The intermediary is a thin local LLM with a system prompt — not separate refine/distill/steer modules.

## Local Components

| Component | Library | Purpose | Size |
|-----------|---------|---------|------|
| VAD | silero-vad | Speech/silence detection | 1MB |
| STT | faster-whisper (base) | Speech → text | 150MB |
| LLM | Ollama qwen2.5:7b | refine + distill + steer | 5GB |
| TTS | Kokoro-82m | Text → audio | 80MB |
| Transport | uvicorn + WebSocket | Audio + control | — |

All work on CPU (GPU optional for real-time speed).

## Hermes Integration (Exact)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat/start` | POST | `{session_id, message}` → `{stream_id}` |
| `/api/chat/stream` | GET | `?stream_id=...` → SSE deltas |
| `/api/chat/steer` | POST | `{session_id, text}` → `{accepted: bool}` |

## Phases

| Phase | Goal | Est. |
|-------|------|------|
| 1 | Text MVP (mock Hermes) | ✅ Done |
| 2 | Voice pipeline (local models) | 2-3 hours |
| 3 | Real Hermes integration (with auth) | 1 hour |
| 4 | Discord bridge | 1 day |
| 5 | WebUI extension | 1 day |

## File Structure

```
intermediary-agent/
├── intermediary/
│   ├── text_intermediary.py    # Text-only intermediary
│   ├── hermes_client.py        # HTTP client for Hermes API
│   ├── distillation.py         # Sentence buffer + distill
│   ├── steering.py             # Barge-in state machine
│   ├── events.py               # IntermediaryEvent schema
│   └── voice/
│       ├── server.py           # FastAPI WebSocket server
│       ├── vad.py              # silero-vad wrapper
│       ├── stt.py              # faster-whisper wrapper
│       ├── tts.py              # Kokoro TTS wrapper
│       ├── llm.py              # Ollama intermediary LLM
│       └── pipeline.py         # Orchestrate VAD→STT→LLM→TTS
├── webui/
│   ├── text_server.py          # Text SSE server
│   ├── templates/
│   │   ├── mvp.html            # Text chat
│   │   └── voice.html          # Voice interface
│   └── static/
│       ├── mvp.css
│       ├── mvp.js
│       └── voice.js
├── tests/                      # 63 passing
├── PROGRESS.md
├── PLAN_PATH_C.md              # DeepThink analysis
└── pyproject.toml
```
