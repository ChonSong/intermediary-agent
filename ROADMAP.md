# Intermediary Agent — Roadmap

## Phase 0: Foundation (Current)

- [x] Create repo structure
- [x] Research LiveKit, Pipecat, TEN Framework
- [x] Research existing hermes-agent `/steer` mechanism
- [x] Load `agent-pipeline-intermediary` skill for reference architectures
- [x] Load `deep-think` skill for empirical validation mandate
- [x] Load `Playwright` skill for video evidence
- [x] Deep-think the implementation architecture (5 loops)
- [x] Write PLAN.md (full implementation plan)
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

### Milestone 1.1: Project Scaffold
- [ ] `pyproject.toml` — Python package with LiveKit dependencies
- [ ] `intermediary/__init__.py` — package init
- [ ] `intermediary/agent.py` — LiveKit `IntermediaryAgent` class
- [ ] `intermediary/hermes_client.py` — `HermesClient` (HTTP + SSE streaming)
- [ ] `intermediary/session.py` — `SessionState` + `SessionManager`
- [ ] `intermediary/prompts.py` — System prompt templates
- [ ] `intermediary/distillation.py` — Buffer + distill logic
- [ ] `intermediary/steering.py` — Barge-in capture (IMMEDIATE POST, not wait)
- [ ] `scripts/dev.sh` — Run locally with LiveKit CLI

### Milestone 1.2: Hermes API Client
- [ ] `HermesClient.create_session()` — POST /api/sessions
- [ ] `HermesClient.start_chat(message)` — POST /api/chat/start → stream_id
- [ ] `HermesClient.stream_chat(stream_id)` — GET /api/chat/stream → AsyncIterable[str]
- [ ] `HermesClient.steer(session_id, text)` — POST /api/chat/steer
- [ ] Handle SSE parsing (`data: {...}\n\n`)
- [ ] Unit tests with mock SSE stream

### Milestone 1.3: Intermediary Agent + LiveKit
- [ ] `IntermediaryAgent` connects to LiveKit room
- [ ] `on_user_speech_committed()` — refine → start Hermes → yield distilled chunks
- [ ] `on_participant_connected()` — create Hermes session
- [ ] `on_participant_disconnected()` — cleanup
- [ ] Forward transcription events to frontend WebSocket

### Milestone 1.4: Distillation Buffer
- [ ] Buffer SSE deltas (1-4 chars) until sentence boundary
- [ ] `has_sentence_boundary()` — detect `.`, `!`, `?`, `:`, `,\s`, `\n`
- [ ] On boundary: pass buffer to distillation LLM
- [ ] Yield distilled text to LiveKit
- [ ] LiveKit Synthesizer handles audio chunking/queueing
- [ ] Unit test: 3-paragraph input → 1-2 sentence output per yield

### Milestone 1.5: Transcript UI
- [ ] `webui/app.py` — FastAPI app serving transcript UI
- [ ] `webui/templates/index.html` — Chat panel layout
- [ ] WebSocket endpoint `/ws/transcript` — forward LiveKit events
- [ ] Render: user messages, intermediary messages, Hermes raw, agent speaking
- [ ] Color coding: user=blue, intermediary=green, hermes=gray

### Milestone 1.6: Barge-in + Steering (CRITICAL TIMING)
- [ ] VAD detects user speech while agent is speaking
- [ ] IMMEDIATELY: `session.stop_speaking()` + POST /api/chat/steer
- [ ] NOT after SSE ends — steer while agent is still running
- [ ] Set `steer_active = true` — drop stale SSE deltas
- [ ] When agent applies steer at tool boundary, clear `steer_active`
- [ ] Resume distillation from new response
- [ ] Integration test: barge-in immediately triggers `/steer` call

### Milestone 1.7: Voice Pipeline
- [ ] LiveKit native STT (Deepgram Nova-3)
- [ ] LiveKit native TTS (Cartesia Sonic-3)
- [ ] Echo cancellation (LiveKit built-in)
- [ ] Turn detection (LiveKit built-in)
- [ ] Connect microphone + speakers

### Milestone 1.8: End-to-End Test
- [ ] Connect to LiveKit room from browser
- [ ] Speak: intermediary refines → sends to Hermes → distills → speaks
- [ ] Verify text transcript shows all exchanges
- [ ] Verify barge-in stops TTS and injects steer IMMEDIATELY (before SSE ends)
- [ ] Record screen video → `test-evidence/videos/phase1-e2e.webm`

### Phase 1 Success Criteria (human-verifiable)

**Test procedure**: Run `scripts/dev.sh`, open browser to `http://localhost:8080`, join LiveKit room, speak.

- [ ] **Connection**: Browser connects to LiveKit room, creates Hermes session
- [ ] **Refine visible**: User speech → refined text shown in transcript
- [ ] **Hermes query**: Refined text sent to Hermes (visible in Hermes logs)
- [ ] **Distill visible**: Hermes response → distilled text → spoken
- [ ] **Transcript complete**: All exchanges visible
- [ ] **Barge-in cuts TTS**: User speaks while agent talking → TTS stops within 200ms
- [ ] **Steer immediate**: POST /api/chat/steer happens BEFORE SSE stream ends (not after)
- [ ] **Steer accepted**: Response shows `accepted: true` (not `stream_dead`)
- [ ] **Hermes adjusts**: Agent changes course based on steer
- [ ] **Latency acceptable**: User speaks → agent responds within 2.5s
- [ ] **Video evidence**: Full E2E flow recorded in `test-evidence/videos/phase1-e2e.webm`

---

## Phase 2: TEN Turn Detection (Optional Enhancement)

**Goal**: Replace LiveKit's default VAD-based turn detection with TEN Turn Detection for better full-duplex behavior.

### Milestone 2.1: TEN Backend
- [ ] Load TEN Turn Detection model from HuggingFace
- [ ] `audio/ten_backend.py` — detect yield-floor, backchannels
- [ ] Config-driven: `audio.backend: livekit|ten`

### Milestone 2.2: Barge-in with TEN
- [ ] User speech detected by TEN → stop TTS immediately
- [ ] TEN determines when user is done speaking

### Phase 2 Success Criteria

- [ ] TEN backend: `audio.backend: ten` → turn detection works
- [ ] Backend swap via config: `livekit` → `ten` (no code changes)
- [ ] Video evidence: full-duplex conversation recorded

---

## Phase 3: Discord Bridge

**Goal**: Bridge LiveKit intermediary to Discord voice channels via existing `VoiceReceiver`.

### Milestone 3.1: Discord Audio Bridge
- [ ] `audio/discord_bridge.py` — bridge `VoiceReceiver` → LiveKit audio pipeline
- [ ] Forward Discord PCM to STT
- [ ] Forward TTS output to Discord voice channel

### Phase 3 Success Criteria

- [ ] Discord VC: Bot joins VC, intermediary works through Discord
- [ ] Steer via text: User can type `/steer` as alternative to voice barge-in

---

## Phase 4: WebUI Extension (Optional)

**Goal**: Integrate with hermes-webui as an extension for text-only users.

### Phase 4 Success Criteria

- [ ] WebUI extension loads intermediary
- [ ] Two-pane composer (raw + refined)
- [ ] Intermediary sidebar (progress updates)

---

## Phase 5: Hardening

### Milestone 5.1: Error Handling
- [ ] Hermes API unreachable → graceful error
- [ ] LLM call failures → pass-through mode
- [ ] LiveKit connection loss → reconnect logic

### Milestone 5.2: Observability
- [ ] Langfuse tracing
- [ ] Per-exchange latency telemetry

### Milestone 5.3: Documentation
- [ ] User guide, developer guide, configuration reference

### Phase 5 Success Criteria

- [ ] Offline recovery: Hermes unreachable → user hears "Hermes is unavailable"
- [ ] Self-diagnostic: `scripts/doctor.sh` reports status
- [ ] No PII in logs

---

## Definition of Done

A phase is complete when:
- [ ] All milestones checked off
- [ ] Tests passing
- [ ] Linting clean
- [ ] Manual E2E test passed (success criteria above)
- [ ] Video evidence recorded
- [ ] Documentation updated

---

## External Dependencies

| Dependency | Repo | Purpose |
|---|---|---|
| LiveKit Agents | [livekit/agents](https://github.com/livekit/agents) | Agent framework, WebRTC, plugins |
| LiveKit Server | [livekit/livekit-server](https://github.com/livekit/livekit-server) | Self-hosted dev server |
| Hermes WebUI | [ChonSong/hermes-webui](https://github.com/ChonSong/hermes-webui) | `/api/chat` SSE stream |
| TEN Framework | [TEN-framework](https://github.com/ten-framework/ten-framework) | Turn detection (Phase 2) |
| Playwright | [playwright](https://playwright.dev/) | Video evidence |
| Deepgram | [deepgram](https://deepgram.com/) | STT provider |
| Cartesia | [cartesia](https://cartesia.ai/) | TTS provider |

---

## Skill Alignment

| Skill | What We Took |
|-------|-------------|
| `agent-pipeline-intermediary` | Architecture pattern, hook signatures, state management |
| `deep-think` | Mandatory empirical validation, barge-in state machine design |
| `Playwright` | Video recording of frontend/voice tests |

---

## Hermes API Endpoints

| Endpoint | Method | Purpose | Notes |
|----------|--------|---------|-------|
| `/api/sessions` | POST | Create session | On participant connect |
| `/api/chat/start` | POST | Start run → stream_id | Main entry point |
| `/api/chat/stream` | GET | SSE deltas | 1-4 chars per delta |
| `/api/chat/steer` | POST | Inject steer | MUST be called WHILE agent running |

---

## File Paths in hermes-webui

| File | Line | Function |
|------|------|----------|
| `api/routes.py` | ~21240 | `_handle_chat_start` |
| `api/routes.py` | ~12895 | `_handle_session_sse_stream` |
| `api/streaming.py` | ~10296 | `_handle_chat_steer` |

No changes to these files are required for Phase 1.
