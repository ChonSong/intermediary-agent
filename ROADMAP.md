# Intermediary Agent — Roadmap

## Phase 0: Foundation ✅

- [x] Create repo structure
- [x] DeepThink Path C (self-hosted voice, no LiveKit)
- [x] Load skills: `agent-pipeline-intermediary`, `deep-think`, `Playwright`
- [x] Write PLAN.md, ROADMAP.md, INTEGRATION.md
- [x] Spike 03: Pure-logic validation (found + fixed 2 bugs)

---

## Phase 1: Text MVP ✅

**Goal**: Working text-only intermediary to prove the pipeline.

| Milestone | Status | Description |
|-----------|--------|-------------|
| 1.1 | ✅ | Scaffold + HermesClient + mock server |
| 1.4 | ✅ | DistillationBuffer + 28 unit tests |
| 1.6a | ✅ | BargeInStateMachine + mock integration |
| 1.5 | ✅ | Transcript UI (FastAPI + WebSocket) |

**Deliverables:**
- `intermediary/text_intermediary.py`, `hermes_client.py`, `distillation.py`, `steering.py`
- `webui/text_server.py`, `templates/mvp.html`, `static/mvp.css`, `mvp.js`
- 63 tests passing

---

## Phase 2: Voice Pipeline (Path C) (NEXT)

**Goal**: Self-hosted voice pipeline. All models local, no API keys.

| Milestone | Description |
|-----------|-------------|
| 2.1 | Install Ollama + local models |
| 2.2 | Voice server: WebSocket audio transport |
| 2.3 | faster-whisper STT integration |
| 2.4 | silero-vad VAD + barge-in |
| 2.5 | Ollama intermediate LLM (refine + distill + steer) |
| 2.6 | Kokoro-82m TTS integration |
| 2.7 | Voice frontend: mic + speakers + WebSocket |
| 2.8 | End-to-end test |

**Est. 2-3 hours**

---

## Phase 3: Real Hermes Integration

**Goal**: Connect voice pipeline to real Hermes API.

| Milestone | Description |
|-----------|-------------|
| 3.1 | Replace mock Hermes with real API |
| 3.2 | Test end-to-end with real Hermes |
| 3.3 | Handle auth errors + 401 recovery |

**Est. 1 hour** (with auth token)

---

## Phase 4: Discord Bridge

**Goal**: Bridge voice pipeline to Discord voice channels.

| Milestone | Description |
|-----------|-------------|
| 4.1 | AudioBackend ABC + Discord bridge |
| 4.2 | Forward Discord PCM → STT |
| 4.3 | Forward TTS → Discord Opus |
| 4.4 | Text channel transcript during VC |
| 4.5 | Steer via text command |

**Est. 1 day**

---

## Phase 5: WebUI Extension

**Goal**: Text-only mode as hermes-webui extension.

| Milestone | Description |
|-----------|-------------|
| 5.1 | Extension manifest |
| 5.2 | Two-pane composer (raw + refined) |
| 5.3 | Intermediary sidebar |

**Est. 1 day**

---

## External Dependencies (All Open Source)

| Dependency | Repo | Purpose | License |
|---|---|---|---|
| Ollama | ollama/ollama | Local LLM inference | MIT |
| faster-whisper | SYSTRAN/faster-whisper | Local STT | MIT |
| Kokoro-82m | hexgrad/kokoro | Local TTS | Apache-2.0 |
| silero-vad | snakers4/silero-vad | Voice activity detection | CC-BY-NC-SA 4.0 |
| Hermes WebUI | ChonSong/hermes-webui | `/api/chat` SSE stream | MIT |
| Playwright | microsoft/playwright | Video evidence | Apache-2.0 |

**No commercial services. No API keys. Zero ongoing cost.**

---

## Test Strategy

| Tier | What | Tool | Against |
|------|------|------|---------|
| **1. Logic** | State machine, distill buffer, refinement, SSE parsing | pytest | Pure Python |
| **2. Mock Integration** | Full pipeline, barge-in timing, steer injection | pytest | Mock Hermes (FastAPI + SSE) |
| **3. E2E** | Real Hermes, real timing, real UI | Playwright | Real servers |

---

## Progress

See `PROGRESS.md` for session-by-session status.

Last update: 2026-07-19
