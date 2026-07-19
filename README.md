# Intermediary Agent

> A LiveKit-based voice intermediary that sits between you and Hermes. Refines messy input, distills verbose output, handles barge-in steering. All through a single system prompt — no separate modules.

---

## Architecture

```
User ↔ LiveKit (WebRTC + STT/TTS/VAD) ↔ VoicePipelineAgent (intermediary LLM) ↔ Hermes API
```

LiveKit handles audio. The intermediary LLM handles meaning. Hermes handles reasoning.

**The intermediary is a thin LLM with one system prompt**, not three Python modules:

1. **Refine**: "um the docker thing?" → "Debug the Docker socket permission error"
2. **Distill**: 3 paragraphs → 1-2 sentences for natural speech
3. **Steer**: inject user corrections mid-turn via existing `/api/chat/steer`

## Quick Start (Development)

### Phase 1: Text MVP (Done)

```bash
cd /home/sc/intermediary-agent
pip install -e .

# Terminal 1: Start text server (uses mock Hermes by default)
python -m uvicorn webui.text_server:app --host 0.0.0.0 --port 8080

# Browser: Open http://localhost:8080
```

### Phase 2: LiveKit Voice (Next)

```bash
# Install LiveKit Go binary (see https://docs.livekit.io/getting-started/installing/)
livekit-server --dev &

# Start voice agent
python -m intermediary.voice_agent
```

### Phase 3: Real Hermes

```bash
export HERMES_MOCK=false
export HERMES_URL=http://127.0.0.1:9119
export HERMES_AUTH_TOKEN=***  # Get from your Hermes dashboard
python -m intermediary.voice_agent
```

## Current Status

| Phase | Status | Tests |
|-------|--------|-------|
| 0 | ✅ Docs, plan, skills loaded | — |
| 1 | ✅ Text MVP (mock Hermes) | 61 passing |
| 2 | 📋 LiveKit voice pipeline | — |
| 3 | 📋 Real Hermes (blocked by auth) | — |
| 4 | 📋 Discord bridge | — |
| 5 | 📋 WebUI extension | — |

## Documentation

| File | Purpose |
|------|---------|
| `README.md` | This file — overview, quick start |
| `PLAN.md` | Full implementation plan (architecture, components, integration) |
| `ROADMAP.md` | Phases, milestones, external dependencies |
| `INTEGRATION.md` | Hermes API endpoints, LiveKit events, config reference |
| `PROGRESS.md` | Session-by-session status |

## Key Decisions

### Why LiveKit (not TEN/Pipecat)?

LiveKit handles all audio plumbing (STT, TTS, VAD, barge-in, echo cancellation). TEN provides better turn-taking for group conversations — unnecessary for single-user agent. Can be reconsidered if VAD feels off.

### Why not replace the intermediary with LiveKit?

LiveKit's `VoicePipelineAgent` chains `STT → LLM → TTS`. The LLM **is** the intermediary. We still need refine/distill/steer behaviors — just encoded in the system prompt, not separate modules.

### Hermes as Separate API

Hermes is an autonomous multi-agent system with memory, toolsets, and context compression. Forcing it into a single function call strips its autonomy. LiveKit = sensory interface (ears + mouth). Hermes = brain.

### No Separate Modules

Refine/distill/steer are one system prompt, not `refine.py`/`distill.py`/`steer.py`. The DistillationBuffer handles 1-4 char SSE deltas → sentence boundaries. That's it.

---

## License

MIT
