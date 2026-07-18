# Intermediary Agent — Roadmap

## Phase 0: Foundation

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

### Phase 0 Success Criteria

- [ ] PLAN.md documents the full LiveKit + Hermes architecture
- [ ] Hermes integration uses existing WebUI API (zero changes to hermes-agent)
- [ ] Audio sublayer is pluggable (TEN/Pipecat/LiveKit)
- [ ] Steering uses barge-in + [User guidance] injection (NOT autonomous drift detection)
- [ ] Test strategy includes video evidence for frontend/voice tests

---

## Phase 1: LiveKit Agent + Hermes API (MVP)

**Goal**: Working intermediary using LiveKit Agent + Hermes WebUI API. User connects to LiveKit room, speaks, intermediary refines → sends to Hermes → distills response → speaks back. User sees full text transcript.

### Milestone 1.1: Project Scaffold
- [ ] `pyproject.toml` — Python package with LiveKit dependencies
- [ ] `intermediary/__init__.py` — package init
- [ ] `intermediary/agent.py` — LiveKit `IntermediaryAgent` class
- [ ] `intermediary/hermes_client.py` — `HermesClient` class for `/api/chat` SSE
- [ ] `intermediary/session.py` — `SessionState` + `SessionManager`
- [ ] `intermediary/prompts.py` — System prompt templates
- [ ] `intermediate/refinement.py` — Refinement logic
- [ ] `intermediary/distillation.py` — LLM Output Replacement for Hermes responses
- [ ] `intermediary/steering.py` — `SteeringController` for barge-in
- [ ] `scripts/dev.sh` — Run locally with LiveKit CLI

### Milestone 1.2: Hermes Client + SSE Streaming
- [ ] `HermesClient.create_session()` — creates Hermes session via `/api/sessions`
- [ ] `HermesClient.send_message()` — POST to `/api/chat`, yields SSE chunks
- [ ] Handle SSE format: `data: {"type": "delta", "content": "..."}`
- [ ] Handle `tool_use`, `thinking`, `error`, `done` event types
- [ ] Unit tests with mock SSE stream

### Milestone 1.3: Intermediary Agent + LiveKit Integration
- [ ] `IntermediaryAgent` connects to LiveKit room
- [ ] `on_user_speech_committed()` handler — refine → Hermes → distill → TTS
- [ ] `on_participant_connected()` — create Hermes session
- [ ] `on_participant_disconnected()` — cleanup
- [ ] Forward transcription events to frontend WebSocket
- [ ] System prompt includes refinement/distillation/steering rules
- [ ] Integration test: connect to room, verify session creation

### Milestone 1.4: Distillation (LLM Output Replacement)
- [ ] `DistillationFilter` class — intercepts Hermes text before TTS
- [ ] Strip `<think>` blocks, markdown, tool JSON
- [ ] Summarize to 1-2 sentences (LLM OR heuristic)
- [ ] Unit test: 3-paragraph input → 1-2 sentence output
- [ ] Handle empty/suppressed output (don't speak)

### Milestone 1.5: Transcript UI
- [ ] `webui/app.py` — FastAPI app serving transcript UI
- [ ] `webui/templates/index.html` — Chat panel layout
- [ ] `webui/static/transcript.js` — LiveKit transcription display
- [ ] WebSocket endpoint `/ws/transcript` — forward LiveKit events to browser
- [ ] Render: user messages, intermediary messages, Hermes raw, agent speaking
- [ ] Render: steer events (highlighted)
- [ ] Color coding: user=blue, intermediary=green, hermes=gray

### Milestone 1.6: Barge-in + Steering
- [ ] `_is_barge_in()` — detect user speech while agent speaking
- [ ] `_handle_barge_in()` — stop TTS, capture text as pending steer
- [ ] Generation ID tracking to discard stale Hermes chunks
- [ ] `maybe_steer()` — inject pending steer after Hermes finishes
- [ ] Integration test: barge-in during TTS → TTS stops → steer sent

### Milestone 1.7: Voice Pipeline
- [ ] LiveKit native STT (Deepgram Nova-3 or similar)
- [ ] LiveKit native TTS (Cartesia Sonic-3 or similar)
- [ ] Echo cancellation (LiveKit built-in)
- [ ] Turn detection (LiveKit built-in)
- [ ] Voice activity detection (VAD)
- [ ] Connect microphone + speakers

### Milestone 1.8: End-to-End Test
- [ ] Connect to LiveKit room from browser
- [ ] Speak: intermediary refines → sends to Hermes → distills → speaks
- [ ] Verify text transcript shows all exchanges
- [ ] Verify barge-in stops TTS and injects steer
- [ ] Record screen video of full flow → `test-evidence/videos/phase1-e2e.webm`

### Phase 1 Success Criteria (human-verifiable)

**Test procedure**: Run `scripts/dev.sh`, open browser to `http://localhost:8080`, join LiveKit room, speak.

- [ ] **Connection**: Browser connects to LiveKit room, creates Hermes session
- [ ] **Refine visible**: User speech → refined text shown in transcript
- [ ] **Hermes query**: Refined text sent to Hermes (visible in Hermes logs)
- [ ] **Distill visible**: Hermes response → distilled text shown + spoken
- [ ] **Transcript complete**: All exchanges (user, intermediary, Hermes raw, agent speaking) visible
- [ ] **Barge-in cuts TTS**: User speaks while agent talking → TTS stops within 200ms
- [ ] **Steer appears**: Barge-in text shown as `[Steer]` in transcript
- [ ] **Steer injected**: After Hermes finishes, steer sent as `[User guidance] <text>`
- [ ] **Hermes adjusts**: Hermes changes course based on steer
- [ ] **Latency acceptable**: User speaks → agent responds within 2 seconds
- [ ] **Video evidence**: Full E2E flow recorded in `test-evidence/videos/phase1-e2e.webm`

---

## Phase 2: Audio Sublayer (TEN Turn Detection)

**Goal**: Replace LiveKit's default turn detection with TEN Turn Detection for better full-duplex behavior (yield floor, backchannels, natural turn-taking).

### Milestone 2.1: Audio Backend Abstraction
- [ ] `audio/base.py` — `AudioBackend` ABC (start_listening, speak, stop_speaking, detect_turn)
- [ ] `audio/livekit_native.py` — LiveKit built-in STT/TTS
- [ ] `audio/ten_backend.py` — TEN Turn Detection integration
- [ ] Config-driven backend selection: `audio.backend: livekit|ten`

### Milestone 2.2: TEN Turn Detection
- [ ] Load TEN Turn Detection model from HuggingFace
- [ ] `detect_turn()` — yield TurnEvent(is_speaking, is_end_of_turn, should_yield_floor)
- [ ] Integrate with intermediary agent: use TEN events instead of LiveKit's

### Milestone 2.3: Barge-in with TEN
- [ ] User speech detected by TEN → stop TTS immediately
- [ ] TEN determines when user is done speaking
- [ ] Intermediary responds after TEN says end-of-turn

### Phase 2 Success Criteria

- [ ] **TEN backend works**: `audio.backend: ten` → turn detection works
- [ ] **Backend swap**: Config change from `livekit` to `ten` → no code changes needed
- [ ] **Natural turn-taking**: Agent knows when to yield without VAD silence timeout
- [ ] **Video evidence**: Full-duplex conversation recorded

---

## Phase 3: Discord Bridge

**Goal**: Bridge LiveKit intermediary to Discord voice channels via existing `VoiceReceiver`.

### Milestone 3.1: Discord Audio Bridge
- [ ] `audio/discord_bridge.py` — bridge `VoiceReceiver` → LiveKit audio pipeline
- [ ] Forward Discord PCM to STT
- [ ] Forward TTS output to Discord voice channel

### Milestone 3.2: Text Channel Integration
- [ ] Text channel shows transcript (same as WebUI transcript)
- [ ] Text channel updates during voice conversation

### Phase 3 Success Criteria

- [ ] **Discord VC**: Bot joins VC, intermediary works through Discord
- [ ] **Text channel transcript**: Text channel shows full conversation
- [ ] **Steer via text**: User can type `/steer` in text channel as alternative to voice barge-in

---

## Phase 4: Pipecat Integration (Concurrent Pipeline)

**Goal**: Use Pipecat for concurrent STT+LLM+TTS to minimize latency.

### Milestone 4.1: Pipecat Backend
- [ ] `audio/pipecat_backend.py` — Pipecat pipeline integration
- [ ] ParallelPipeline: STT, intermediary LLM, TTS running concurrently
- [ ] Barge-in via Pipecat's built-in interruption handling

### Milestone 4.2: Latency Optimization
- [ ] Target: <500ms from user speech end to agent speech start
- [ ] Compare: LiveKit native vs TEN vs Pipecat latency

### Phase 4 Success Criteria

- [ ] **Pipecat backend works**: `audio.backend: pipecat` → concurrent pipeline
- [ ] **Sub-500ms latency**: Agent starts responding <500ms after user stops speaking

---

## Phase 5: WebUI Extension (Optional)

**Goal**: If needed, integrate with hermes-webui as an extension for users who already use WebUI.

### Phase 5 Success Criteria

- [ ] WebUI extension loads intermediary
- [ ] Two-pane composer (raw + refined)
- [ ] Intermediary sidebar (progress updates)

---

## Phase 6: Hardening & Polish

### Milestone 6.1: Error Handling
- [ ] Hermes API unreachable → graceful error message
- [ ] LLM call failures → pass-through mode
- [ ] LiveKit connection loss → reconnect logic
- [ ] Rate limit handling

### Milestone 6.2: Observability
- [ ] Langfuse tracing integration
- [ ] Per-exchange latency telemetry
- [ ] Drift event logging

### Milestone 6.3: Documentation
- [ ] User guide
- [ ] Developer guide
- [ ] Configuration reference

### Phase 6 Success Criteria

- [ ] **Offline recovery**: Hermes unreachable → user hears "Hermes is unavailable"
- [ ] **Self-diagnostic**: `scripts/doctor.sh` reports status
- [ ] **No PII in logs**: User messages not logged at INFO level

---

## Phase 7: Research & Advanced Features

### Milestone 7.1: Multi-Turn Refinement
- [ ] Cross-turn pronoun tracking
- [ ] Reference resolution across 5+ turns

### Milestone 7.2: Proactive Suggestions
- [ ] Intermediary suggests follow-up questions
- [ ] Pre-fetch likely needed context

### Milestone 7.3: User Model
- [ ] Learn preferred communication style
- [ ] Adapt distillation level per user

---

## Definition of Done

A phase is complete when:
- [ ] All milestones checked off
- [ ] Tests passing
- [ ] Linting clean
- [ ] Manual E2E test passed (success criteria above)
- [ ] Video evidence recorded for each platform
- [ ] Documentation updated

---

## External Dependencies

| Dependency | Repo | Status | Use Case |
|---|---|---|---|
| LiveKit Agents | [livekit/agents](https://github.com/livekit/agents) | 🆕 New | Agent framework, WebRTC, STT/TTS plugins |
| LiveKit Server | [livekit/livekit-server](https://github.com/livekit/livekit-server) | 🆕 New | Self-hosted LiveKit server for dev |
| Hermes WebUI API | [ChonSong/hermes-webui](https://github.com/ChonSong/hermes-webui) | ✅ Existing | `/api/chat` SSE stream, `/api/sessions` |
| TEN Framework | [TEN-framework](https://github.com/ten-framework/ten-framework) | 🆕 New | Full-duplex turn detection |
| TEN Turn Detection | [HuggingFace](https://huggingface.co/TEN-framework/TEN_Turn_Detection) | 🆕 New | Yield-floor detection |
| Pipecat | [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | 🆕 New | Concurrent STT+LLM+TTS pipeline |
| Playwright | [playwright](https://playwright.dev/) | 🆕 New | Video evidence for frontend/voice tests |
| Deepgram | [deepgram](https://deepgram.com/) | 🆕 New | STT provider (LiveKit plugin) |
| Cartesia | [cartesia](https://cartesia.ai/) | 🆕 New | TTS provider (LiveKit plugin) |

---

## Hermes API Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sessions` | POST | Create new session |
| `/api/sessions` | GET | List sessions |
| `/api/chat` | POST | Send message → SSE stream |
| `/api/chat/steer` | POST | Inject steer (alternative: next message) |

### SSE Stream Format

```
data: {"type": "delta", "content": "First, let me check"}

data: {"type": "tool_use", "tool": "read_file", "args": {"path": "/var/log/syslog"}}

data: {"type": "done"}
```

---

## Skill Alignment

| Skill | What We Took |
|-------|-------------|
| `agent-pipeline-intermediary` | Architecture pattern, hook signatures, state management, prompt templates |
| `deep-think` | Mandatory empirical validation, barge-in state machine design, 5-loop architecture decision |
| `Playwright` | Video recording of frontend/voice tests for human-verifiable evidence |
