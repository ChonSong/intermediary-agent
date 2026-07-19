# Intermediary Agent — Roadmap

## Phase 0: Foundation

- [x] Create repo structure
- [x] Research LiveKit (TEN ruled out — LiveKit built-in VAD sufficient for single-user)
- [x] Research existing hermes-agent `/steer` mechanism
- [x] Load `agent-pipeline-intermediary` skill for reference
- [x] Load `deep-think` skill for empirical validation
- [x] Load `Playwright` skill for video evidence
- [x] Write PLAN.md, ROADMAP.md, INTEGRATION.md
- [x] Spike 03: Pure-logic validation (found + fixed 2 bugs)

---

## Phase 1: Text MVP (DONE)

**Goal**: Working text-only intermediary to prove the pipeline.

| Milestone | Status | Description |
|-----------|--------|-------------|
| 1.1 | ✅ | Scaffold + HermesClient + mock server |
| 1.4 | ✅ | DistillationBuffer + 28 unit tests |
| 1.6a | ✅ | BargeInStateMachine + mock integration |
| 1.5 | ✅ | Transcript UI (FastAPI + WebSocket) |
| 1.6b | 📋 | Live integration test ready (need auth token) |
| 1.7 | 📋 | Voice pipeline (Phase 2) |

**Deliverables:**
- `intermediary/text_intermediary.py` — TextIntermediary core
- `intermediary/hermes_client.py` — Hermes HTTP client
- `intermediary/distillation.py` — Sentence buffer + distill
- `intermediary/steering.py` — Barge-in state machine
- `webui/text_server.py` — FastAPI server with SSE
- `webui/templates/mvp.html` — Dark theme chat interface
- `tests/test_text_mvp.py` — 9 tests (61 total passing)

---

## Phase 2: LiveKit Voice Pipeline (NEXT)

**Goal**: Replace text input with LiveKit audio pipeline. Same architecture, different transport.

**Architecture:**
```
User ↔ LiveKit (WebRTC + STT/TTS/VAD) ↔ VoicePipelineAgent (intermediary LLM) ↔ Hermes API
```

**What LiveKit provides:**
- STT (Deepgram Nova-3)
- TTS (Cartesia Sonic-3)
- VAD (voice activity detection)
- Barge-in (`session.interrupt()`)
- Turn-taking (silence-based)
- Echo cancellation
- WebRTC transport

**What we add:**
- `intermediary/voice_agent.py` — VoicePipelineAgent wiring
- `intermediary/hermes_tools.py` — `query_hermes` function_tool
- System prompt encodes refine/distill/steer

| Milestone | Description |
|-----------|-------------|
| 2.1 | Install LiveKit Go binary + start dev server |
| 2.2 | Create voice agent with system prompt |
| 2.3 | Wire query_hermes as function_tool |
| 2.4 | Distillation per sentence (buffer → distill → TTS) |
| 2.5 | Barge-in → steer forwarding |
| 2.6 | Frontend: mic button + live transcript |
| 2.7 | Video evidence: screen recording |

**Est. 4-6 hours**

---

## Phase 3: Real Hermes Integration

**Goal**: Connect voice pipeline to real Hermes API.

**Prerequisites:**
- Auth token from Hermes dashboard (port 9119)
- `HERMES_AUTH_TOKEN` env var

| Milestone | Description |
|-----------|-------------|
| 3.1 | Replace mock Hermes with real API |
| 3.2 | Test end-to-end with real Hermes |
| 3.3 | Handle auth errors + 401 recovery |

**Est. 1 hour**

---

## Phase 4: Discord Bridge

**Goal**: Bridge LiveKit intermediary to Discord voice channels.

| Milestone | Description |
|-----------|-------------|
| 4.1 | AudioBackend ABC + Discord bridge |
| 4.2 | Forward Discord PCM → LiveKit STT |
| 4.3 | Forward LiveKit TTS → Discord Opus |
| 4.4 | Text channel transcript during VC conversation |
| 4.5 | Steer via text (`/steer` command) |

**Est. 1 day**

---

## Phase 5: WebUI Extension

**Goal**: Text-only mode as hermes-webui extension.

| Milestone | Description |
|-----------|-------------|
| 5.1 | Extension manifest |
| 5.2 | Two-pane composer (raw + refined) |
| 5.3 | Intermediary sidebar |
| 5.4 | SSE endpoint `/api/intermediary/stream` |

**Est. 1 day**

---

## External Dependencies

| Dependency | Repo | Purpose |
|---|---|---|
| LiveKit Agents | [livekit/agents](https://github.com/livekit/agents) | Agent framework, WebRTC, plugins |
| LiveKit Server | [livekit/livekit-server](https://github.com/livekit/livekit-server) | Self-hosted dev server (Go binary) |
| Hermes WebUI | [ChonSong/hermes-webui](https://github.com/ChonSong/hermes-webui) | `/api/chat` SSE stream |
| Playwright | [playwright](https://playwright.dev/) | Video evidence |
| Deepgram | [deepgram](https://deepgram.com/) | STT provider |
| Cartesia | [cartesia](https://cartesia.ai/) | TTS provider |

---

## Test Strategy

| Tier | What | Tool | Against |
|------|------|------|---------|
| **1. Logic** | State machine, distill buffer, refinement, SSE parsing | pytest | Pure Python |
| **2. Mock Integration** | Full pipeline, barge-in timing, steer injection | pytest | Mock Hermes (FastAPI + SSE) |
| **3. E2E + Telemetry** | Real audio, real timing, real UI | Playwright + `time.perf_counter()` | Real LiveKit + Real Hermes |

---

## Progress

See `PROGRESS.md` for session-by-session status.

Last update: 2026-07-19
