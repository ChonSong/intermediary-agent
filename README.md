# Intermediary Agent

> A self-hosted voice intermediary between you and Hermes. Refines messy input, distills verbose output, handles barge-in steering. Zero third-party API dependencies — runs entirely on your machine.

---

## Architecture

```
Browser (mic/speakers) ⟷ WebSocket ⟷ Voice Server (Python) ⟷ Hermes API
     getUserMedia()          PCM frames        STT → LLM → TTS
     WebRTC AEC                              (all local)
```

**All components run locally:**
- **STT**: faster-whisper (speech → text)
- **LLM**: Ollama qwen2.5:7b (intermediary: refine + distill + steer)
- **TTS**: Kokoro-82m (text → audio)
- **VAD**: silero-vad (speech/silence detection)
- **Hermes**: Your existing API (reasoning)

**No LiveKit. No Deepgram. No Cartesia. No OpenAI. No API keys.**

## Quick Start

### Prerequisites

```bash
# Install Ollama (https://ollama.com)
ollama pull qwen2.5:7b

# Install Kokoro TTS (https://github.com/hexgrad/kokoro)
pip install kokoro

# Install faster-whisper
pip install faster-whisper

# Install other deps
pip install -e ".[voice]"
```

### Run

```bash
# Terminal 1: Start voice server
cd /home/sc/intermediary-agent
python -m intermediary.voice.server

# Terminal 2: Start text server (optional, for text-only mode)
python -m uvicorn webui.text_server:app --host 0.0.0.0 --port 8080

# Browser: Open http://localhost:8080
# Click mic button → speak → hear response
```

## Current Status

| Phase | What | Status | Tests |
|-------|------|--------|-------|
| 0 | Docs, plan, skills loaded | ✅ Done | — |
| 1 | Text MVP (mock Hermes) | ✅ Done | 63 passing |
| 2 | Voice pipeline (local models) | 📋 Planned | — |
| 3 | Real Hermes integration | 📋 Planned | — |
| 4 | Discord bridge | 📋 Planned | — |
| 5 | WebUI extension | 📋 Planned | — |

## Documentation

| File | Purpose |
|------|---------|
| `README.md` | This file — overview, quick start |
| `PLAN.md` | Full implementation plan (architecture, components, integration) |
| `PLAN_PATH_C.md` | DeepThink analysis of self-hosted voice path |
| `ROADMAP.md` | Phases, milestones, external dependencies |
| `INTEGRATION.md` | Hermes API endpoints, config reference |
| `PROGRESS.md` | Session-by-session status |

## Key Decisions

### Why Self-Hosted (No LiveKit)?

LiveKit requires commercial providers (Deepgram/OpenAI/Cartesia) for speech. Local models give same quality, full privacy, zero ongoing cost, and one less dependency to manage.

### Why Not Web Speech API?

Web Speech API TTS is clearly robotic (user rejected it). It also sends audio to Google — not private despite being "browser-native." Local Kokoro TTS is higher quality and fully private.

### Hermes as Separate API

Hermes is an autonomous multi-agent system with memory, toolsets, and context compression. The intermediary is a thin LLM that handles voice I/O and meaning — Hermes handles reasoning.

### No Separate Modules

Refine/distill/steer are one system prompt, not `refine.py`/`distill.py`/`steer.py`. The DistillationBuffer handles 1-4 char SSE deltas → sentence boundaries. That's it.

## Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 8GB | 16GB |
| Disk | 5GB | 10GB |
| GPU | Optional (CPU works) | NVIDIA for real-time |

All components work on CPU. GPU makes STT/TTS real-time (<500ms).

## License

MIT
