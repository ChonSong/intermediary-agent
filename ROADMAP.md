# Intermediary Agent — Roadmap

## Phase 0: Foundation (Current)

- [x] Create repo structure
- [x] Research LiveKit, Pipecat, TEN Framework
- [x] Research existing hermes-agent `/steer` mechanism
- [x] Load `agent-pipeline-intermediary` skill for reference architectures
- [x] Load `deep-think` skill for empirical validation mandate
- [x] Load `Playwright` skill for video evidence
- [x] Deep-think the implementation architecture (5 loops)
- [x] Identify testing blind spots (mocking real-time audio, async state sync)
- [x] Write PLAN.md (full implementation plan, corrected)
- [x] Write ROADMAP.md (this file)
- [x] Write INTEGRATION.md
- [ ] Set up development environment
- [ ] Create test scaffolding

---

## Phase 1: LiveKit Agent + Hermes API (MVP)

**Goal**: Working LiveKit agent that:
- Refines messy input via system prompt
- Pipes Hermes SSE through distillation buffer → LiveKit TTS
- Captures barge-in → IMMEDIATELY POST /api/chat/steer (NOT after SSE ends)
- Shows full text transcript in browser

### Session 1: Core Scaffolding + Mock Hermes (Phases 1.1–1.3)

**Goal**: Build the foundation with a mock Hermes server from day one.

**Skills**: `agent-pipeline-intermediary` (reference patterns), LiveKit Agents SDK, `httpx` async streams

- [ ] `pyproject.toml` — Python package with LiveKit dependencies
- [ ] `intermediary/__init__.py` — package init
- [ ] `intermediary/hermes_client.py` — `HermesClient` for `/api/chat` SSE
- [ ] `intermediary/agent.py` — LiveKit `IntermediaryAgent` class
- [ ] `intermediary/session.py` — `SessionState` (generation counter, steer_active)
- [ ] `conftest.py` — **Mock Hermes server** (FastAPI app mimicking `/api/chat` SSE stream)
- [ ] Integration test: Agent connects to room, reads simulated SSE deltas from mock server

**Deliverable**: Local lightweight mock Hermes server + basic LiveKit Agent connecting and reading simulated SSE text deltas.

### Session 2: Text Distillation + Logic Verification (Phase 1.4)

Skills: Deterministic text chunking, `pytest`

- [ ] `intermediary/distillation.py` — Sentence boundary detection + distill logic
- [ ] `intermediary/prompts.py` — System prompt templates
- [ ] `tests/test_distillation.py` — Sentence buffer unit tests
- [ ] `tests/test_refinement.py` — Pronoun resolution + intent clarification tests
- [ ] `tests/test_hermes_client.py` — SSE parsing tests against mock server
- [ ] Tier 1 coverage: All state machine transitions, distillation buffer, refinement

**Deliverable**: Sentence boundary aggregator + distillation LLM pipeline with full Tier 1 unit tests.

### Session 3: State-Steering Engine (Phase 1.6 Part A)

**Skills**: `asyncio` concurrency primitives, `deep-think` (state machine design)

- [ ] `intermediary/steering.py` — `SteeringController` (async events, generation tracking)
- [ ] `BargeInStateMachine` — LISTENING → SPEAKING → STALE → INJECT transitions
- [ ] `SessionState` with `asyncio.Event` + per-session lock for cross-loop sync
- [ ] `tests/test_steering.py` — Barge-in state machine unit tests
- [ ] Tier 2 mock integration: Full pipeline flow with mock Hermes (deterministic chunk delays)
- [ ] Verify: Barge-in stops TTS + POSTs steer IMMEDIATELY (before SSE ends)
- [ ] Verify: Stale deltas dropped after barge-in; new response triggers resume

**Deliverable**: VAD state machine logic that instantly flags incoming text delta stream as "stale". Full Tier 2 mock integration tests.

### Session 4: WebUI Pipeline Integration (Phase 1.6 Part B)

Skills: LiveKit WebUI API integration, real server testing

- [ ] Point agent at real Hermes WebUI endpoints
- [ ] Verify: Real `/api/chat/start` + `/api/chat.stream` SSE works
- [ ] Verify: Real `/api/chat/steer` injection works
- [ ] Integration test: Real Hermes + barge-in steer

**Deliverable**: Agent pointed at real Hermes WebUI endpoints. Live steering verified.

### Session 5: Voice + UI Layer (Phases 1.5 + 1.7)

Skills: Chromium audio injection flags, audio profiles, LiveKit audio

- [ ] LiveKit native STT (Deepgram Nova-3) + TTS (Cartesia Sonic-3)
- [ ] `webui/app.py` — FastAPI transcript UI
- [ ] `webui/templates/index.html` — Chat panel layout
- [ ] `webui/static/transcript.js` — LiveKit transcription display
- [ ] WebSocket endpoint `/ws/transcript` — forward LiveKit events
- [ ] Real microphone/speaker wiring via LiveKit
- [ ] Chromium audio injection flags (`--use-fake-device-for-media-stream`)
- [ ] `tests/test_transcript_ui.py` — Playwright UI validation

**Deliverable**: Real microphone/speaker data via LiveKit. UI page showing status values.

### Session 6: Telemetry, Verification + Video (Phase 1.8)

Skills: Structured log telemetry (`time.perf_counter()`), Playwright context configs

- [ ] Telemetry class with high-resolution timestamps
- [ ] Timing logs for barge-in TTS cut-off, steer POST, delta drop, new response
- [ ] Playwright E2E test with Chromium audio injection
- [ ] Screen recording of full E2E flow → `test-evidence/videos/phase1-e2e.webm`
- [ ] Verify all success criteria via telemetry logs + video

**Deliverable**: Audio injection flags configured. Playwright script fired. Timing logs output. Screen recording of full E2E flow.

---

## Phase 2: TEN Turn Detection (Optional Enhancement)

**Goal**: Replace LiveKit's default VAD-based turn detection with TEN Turn Detection for better full-duplex behavior.

| Milestone | Tasks |
|-----------|-------|
| 2.1 TEN Backend | Load TEN Turn Detection model. `audio/ten_backend.py`. Detect yield-floor. |
| 2.2 Barge-in with TEN | User speech detected by TEN → stop TTS immediately. TEN determines end-of-turn. |
| 2.3 Config swap | `audio.backend: livekit` → `audio.backend: ten` (no code changes) |

---

## Phase 3: Discord Bridge

**Goal**: Bridge LiveKit intermediary to Discord voice channels via existing `VoiceReceiver`.

| Milestone | Tasks |
|-----------|-------|
| 3.1 Discord Audio Bridge | `audio/discord_bridge.py` — bridge `VoiceReceiver` → LiveKit audio pipeline |
| 3.2 Text Channel Integration | Text channel shows transcript during voice conversation |
| 3.3 Steer via Text | User can type `/steer` in text channel as alternative to voice barge-in |

---

## Phase 4: Pipecat Integration (Optional)

**Goal**: Use Pipecat for concurrent STT+LLM+TTS to minimize latency.

| Milestone | Tasks |
|-----------|-------|
| 4.1 Pipecat Backend | `audio/pipecat_backend.py` — Pipecat pipeline integration |
| 4.2 Latency Optimization | Target: <500ms from user speech end to agent speech start |

---

## Phase 5: Hardening

| Milestone | Tasks |
|-----------|-------|
| 5.1 Error Handling | Hermes unreachable → graceful error. LLM failures → pass-through mode. |
| 5.2 Observability | Langfuse tracing. Per-exchange latency telemetry. |
| 5.3 Documentation | User guide, developer guide, configuration reference |

---

## Definition of Done

A phase is complete when:
- [ ] All milestones checked off
- [ ] Tests passing
- [ ] Linting clean
- [ ] Manual E2E test passed (success criteria)
- [ ] Video evidence recorded
- [ ] Documentation updated

---

## External Dependencies

| Dependency | Repo | Purpose |
|---|---|---|
| LiveKit Agents | [livekit/agents](https://github.com/livekit/agents) | Agent framework, WebRTC, plugins |
| Hermes WebUI | [ChonSong/hermes-webui](https://github.com/ChonSong/hermes-webui) | `/api/chat` SSE stream |
| Playwright | [playwright](https://playwright.dev/) | Video evidence for frontend/voice tests |
| Deepgram | [deepgram](https://deepgram.com/) | STT provider |
| Cartesia | [cartesia](https://cartesia.ai/) | TTS provider |
| TEN Framework | [TEN-framework](https://github.com/ten-framework/ten-framework) | Turn detection (Phase 2) |
| Pipecat | [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | Concurrent pipeline (Phase 4) |

---

## Skills Reference

| Skill | Phases | What We Take |
|-------|--------|-------------|
| `agent-pipeline-intermediary` | 1.1–1.6 | Architecture pattern, hook signatures, session mapping, prompt templates, steering mechanism |
| `deep-think` | 1.6 (barge-in), 1.4 (distillation) | State machine design, async synchronization patterns, empirical validation mandate |
| `Playwright` | 1.5, 1.7, 1.8 | Video recording of frontend/voice tests, UI validation, Chromium audio injection flags |

---

## Hermes API Quick Reference

| Endpoint | Method | Purpose | Notes |
|----------|--------|---------|-------|
| `/api/sessions` | POST | Create session | On participant connect |
| `/api/chat/start` | POST | Start run → stream_id | Main entry point |
| `/api/chat/stream` | GET | SSE deltas (1-4 chars each) | Buffer before distill |
| `/api/chat/steer` | POST | Inject steer | **MUST** be called WHILE agent running |

---

## Test Strategy Summary

| Tier | What | Tool | Runs Against |
|------|------|------|--------------|
| **1. Logic** | State machine, distill buffer, refinement, SSE parsing | pytest | Nothing (pure Python) |
| **2. Mock Integration** | Full pipeline, barge-in timing, steer injection | pytest | Mock Hermes (FastAPI + SSE) |
| **3. E2E + Telemetry** | Real audio, real timing, real UI | Playwright + `time.perf_counter()` | Real LiveKit + Real Hermes |

### Test Evidence Storage

```
test-evidence/
  videos/
    phase1-session1-agent-connect.webm
    phase1-session2-distillation.webm
    phase1-session3-steering.webm
    phase1-session4-live-hermes.webm
    phase1-session5-voice-pipeline.webm
    phase1-session6-full-e2e.webm
  screenshots/
    transcript-ui.png
  logs/
    telemetry-{timestamp}.jsonl
```
