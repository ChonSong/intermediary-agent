# Intermediary Agent — Roadmap

## Phase 0: Foundation (Current)

- [x] Create repo structure
- [x] Write PLAN.md (architecture, components, integration points)
- [x] Write ROADMAP.md (this file)
- [x] Write INTEGRATION.md (file paths, function signatures)
- [x] Research existing /steer mechanism
- [x] Research full-duplex audio frameworks (TEN, Pipecat, LiveKit)
- [x] Load `agent-pipeline-intermediary` skill for reference architecture
- [x] Load `Playwright` skill for test evidence (screenshots + video)
- [x] Load `deep-think` skill for mandatory empirical validation
- [ ] Set up development environment (venv, dependencies)
- [ ] Create test scaffolding

### Phase 0 Success Criteria (human-verifiable)

- [ ] Repo README explains what we are building
- [ ] PLAN.md has architecture diagram, component design, prompts, DeepThink analysis
- [ ] ROADMAP.md references existing `agent-pipeline-intermediary` skill patterns
- [ ] Steering plan hooks into `agent.steer()` (NOT reinvented)
- [ ] Audio is pluggable sublayer (TEN/Pipecat/LiveKit)
- [ ] INTEGRATION.md has exact file paths for hermes-agent and hermes-webui
- [ ] Repository is public on GitHub

---

## Phase 1: Hermes-Agent Plugin (Text Only, Discord)

**Goal**: Working intermediary as a hermes-agent plugin. Text input only. Discord surface. No audio.

### Milestone 1.1: Plugin Scaffold
- [ ] `intermediary/__init__.py` — register() entry point using pattern from skill
- [ ] `intermediary/plugin.yaml` — manifest
- [ ] `intermediary/config.py` — config schema
- [ ] `intermediary/state.py` — IntermediaryState dataclass (pattern from skill)
- [ ] Unit tests for state management

**Files**:
```
intermediary/
  __init__.py
  plugin.yaml
  config.py
  state.py
tests/
  test_state.py
```

### Milestone 1.2: Refine Engine
- [ ] `intermediary/refine.py` — LLM call to refine input
- [ ] `prompts/refine_system.md` — refinement prompt template
- [ ] Conversation context + pronoun resolution (using `intent_history`)
- [ ] Unit tests with mocked LLM

### Milestone 1.3: Hook Integration
- [ ] `intermediary/hooks.py` — register `pre_gateway_dispatch`, `pre_llm_call`, `post_llm_call`
- [ ] Wire: incoming → refine → replace `event.text` → agent processes
- [ ] Wire: `pre_llm_call` → inject steering if drift detected
- [ ] Wire: `post_llm_call` → distill response → surface
- [ ] Integration test with mock hermes-agent

### Milestone 1.4: Discord Surface
- [ ] `surfaces/discord_surface.py` — edit-message pattern using existing `DiscordAdapter.edit_message()`
- [ ] send_refined(), start_progress(), update_progress(), send_final()
- [ ] Rate-limited edits (500ms interval)
- [ ] Mock Discord channel tests

### Milestone 1.5: Distill Engine
- [ ] `intermediary/distill.py` — buffer agent output, produce progress updates
- [ ] `prompts/distill_system.md` — distillation prompt template
- [ ] Milestone detection (topic shifts, completions)
- [ ] Unit tests with mock streaming

### Milestone 1.6: Steer Engine (using existing `agent.steer()`)
- [ ] `intermediary/steer.py` — detect drift, inject via `agent.steer()` mechanism
- [ ] `prompts/steer_system.md` — drift detection prompt
- [ ] Rate-limited: max 1 steer injection per exchange
- [ ] Mock test: verify agent receives steer text after tool call

### Milestone 1.7: End-to-End Text Test
- [ ] Run with real hermes-agent in Discord DM
- [ ] Verify: raw → refined → progress updates → final summary
- [ ] Tune prompts based on real outputs
- [ ] Record screen video of Discord E2E flow (human evidence)

### Phase 1 Success Criteria (human-verifiable)

**Test procedure**: Enable intermediary in a real Discord DM with the bot. Send text messages. Watch the bot response.

- [ ] **Refine displays**: Bot sends the refined version of your messy text before its main response
- [ ] **Edit pattern**: Bot edits its original message to update progress, not spam new messages
- [ ] **Progress updates concise**: A long agent response (<500 tokens) generates ≤3 progress updates
- [ ] **Final summary appears**: After agent finishes, intermediary shows a single-line summary
- [ ] **Latency**: Refined text appears within 1 second of hitting Enter
- [ ] **No-agent fallback**: Disabling intermediary plugin doesn't break normal bot
- [ ] **Pronoun resolution**: After discussing Docker, sending "ok what about that?" references "Docker permission error"
- [ ] **Steer non-interrupting**: When agent goes off-topic, it receives correction WITHOUT interruption. User sees agent adjust course mid-response
- [ ] **Video evidence**: Screen recording of Discord E2E flow is in `test-evidence/videos/phase1-e2e.webm`

---

## Phase 2: Voice Input (Discord)

**Goal**: Voice input via existing hermes-agent VoiceReceiver + STT.

### Milestone 2.1: Audio Backend Abstraction
- [ ] `audio/base.py` — AudioBackend ABC (start_listening, speak, stop_speaking, detect_turn)
- [ ] `audio/ten_backend.py` — TEN Turn Detection integration
- [ ] Mock audio backend for testing

### Milestone 2.2: Voice-to-Refined Pipeline
- [ ] Bridge VoiceReceiver output → intermediary refine engine
- [ ] STT → raw transcript → refine → send refined to agent
- [ ] Surface: "Transcribing..." → "Refined: ..." → "Sending..."

### Milestone 2.3: Barge-in
- [ ] When user speaks while agent is talking: stop TTS immediately
- [ ] TEN Turn Detection for determining when user is done speaking
- [ ] Surface: "Interrupted. Listening..."

### Milestone 2.4: Backend Swap Test
- [ ] Config change: `audio.backend: ten` → works
- [ ] Config change: `audio.backend: mock` → works
- [ ] Same intermediary logic regardless of backend

### Phase 2 Success Criteria (human-verifiable)

**Test procedure**: Join Discord voice channel. Speak to the bot. Watch text channel updates.

- [ ] **Voice transcribes**: Speaking in VC causes bot to transcribe and show raw transcript in text channel
- [ ] **Refinement visible**: Refined transcript appears before bot's response
- [ ] **Barge-in works**: Start speaking while bot is replying → bot stops talking within 200ms
- [ ] **Turn detection**: Bot knows when you're done speaking, doesn't cut you off
- [ ] **No self-hearing**: Bot's own TTS output doesn't trigger its own STT
- [ ] **Video evidence**: Screen recording of Discord voice flow is in `test-evidence/videos/phase2-voice-e2e.webm`

---

## Phase 3: Steering Deep-Dive

**Goal**: Full drift detection and correction via `agent.steer()`.

### Milestone 3.1: Drift Detection Calibration
- [ ] `intermediary/steer.py` — compare streaming output to user_intent baseline
- [ ] Confidence scoring (don't intervene too early)
- [ ] Test with real off-topic agent responses

### Milestone 3.2: Integration with `agent.steer()`
- [ ] Verify plugin can call `agent.steer()` (or `ctx.steer_agent(session_id, text)`)
- [ ] If direct `agent.steer()` is not accessible from plugin, add `PluginContext.steer_agent()` method
- [ ] Verify injection appears in next tool result as `User guidance: ...`

### Milestone 3.3: Rate Limiting
- [ ] Max 1 steer injection per exchange
- [ ] Don't over-steer (let agent explore productively)
- [ ] Track injection history

### Phase 3 Success Criteria (human-verifiable)

**Test procedure**: Ask bot a question that might elicit off-topic info. Verify non-interrupting correction.

- [ ] **Steering triggers on drift**: When bot starts going off-topic, intermediary injects correction (visible in logs)
- [ ] **Non-interrupting**: Agent continues its turn, adjusts course, doesn't restart
- [ ] **Progress shows redirection**: Intermediary updates progress message to mention redirection
- [ ] **No over-steering**: Bot exploring related-but-useful context does NOT trigger steering
- [ ] **Video evidence**: Screen recording of steering correction is in `test-evidence/videos/phase3-steer-e2e.webm`

---

## Phase 4: WebUI Extension

**Goal**: Two-pane composer + intermediary sidebar + browser voice.

### Milestone 4.1: Extension Scaffold
- [ ] `webui_extension/` — manifest, CSS, JS (pattern from skill)
- [ ] Register with hermes-webui extension system
- [ ] SSE connection to intermediary API

### Milestone 4.2: Two-Pane Composer
- [ ] Raw transcript pane (top, grayed)
- [ ] Refined pane (bottom, editable)
- [ ] Real-time update as user types/speaks

### Milestone 4.3: Intermediary Sidebar
- [ ] Progress updates during agent response
- [ ] Steering notifications
- [ ] Final summary card

### Milestone 4.4: Playwright Tests with Video Evidence
- [ ] Write Playwright test: two-pane composer renders
- [ ] Write Playwright test: real-time refinement as user types
- [ ] Write Playwright test: sidebar shows progress updates
- [ ] Write Playwright test: settings persist across reload
- [ ] All tests record video to `test-evidence/videos/webui-{test-name}.webm`

### Phase 4 Success Criteria (human-verifiable)

**Test procedure**: Run Playwright tests. Watch video evidence.

- [ ] **Two-pane visible**: Composer has raw + refined panes (screenshot in `test-evidence/screenshots/webui-two-pane.png`)
- [ ] **Real-time refinement**: As you type "um the docker thing?", refined pane shows "Debug the Docker permission error" within 500ms (video evidence)
- [ ] **Editable refined**: Click into refined pane, edit, send YOUR text (video evidence)
- [ ] **Sidebar progress**: During long agent response, sidebar shows progress updates (video evidence)
- [ ] **Settings persist**: Toggle "refine" off → reload → still off (screenshot evidence)
- [ ] **Playwright video**: Full E2E WebUI flow recorded in `test-evidence/videos/webui-full-e2e.webm`

---

## Phase 5: CLI/TUI Surface

**Goal**: Terminal interface.

### Milestone 5.1: CLI Surface
- [ ] `surfaces/cli_surface.py` — status line updates
- [ ] Refined transcript confirmation before send

### Phase 5 Success Criteria (human-verifiable)

- [ ] **Status line**: During agent response, status updates
- [ ] **Refined confirmation**: Shows refined prompt, [y/n] to send
- [ ] **Color coding**: Green ✓, red ✗, yellow ⟳

---

## Phase 6: Hardening & Polish

### Milestone 6.1: Error Handling
- [ ] LLM call failures → pass-through mode
- [ ] Audio backend failures → fall back to text
- [ ] Rate limit handling

### Milestone 6.2: Observability
- [ ] Langfuse tracing integration
- [ ] Per-exchange latency telemetry
- [ ] Drift event logging

### Milestone 6.3: Documentation
- [ ] User guide
- [ ] Developer guide (explains DeepThink rationale)
- [ ] Configuration reference

### Phase 6 Success Criteria (human-verifiable)

- [ ] **Offline recovery**: LLM provider unreachable → conversation still works (pass-through)
- [ ] **Self-diagnostic**: `hermes intermediary doctor` reports status
- [ ] **No PII in logs**: User messages not logged at INFO level
- [ ] **Video evidence**: All E2E flows have corresponding video in `test-evidence/videos/`

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

## Test Evidence Storage

All video and screenshot evidence is stored in:

```
test-evidence/
  videos/
    phase1-e2e.webm
    phase2-voice-e2e.webm
    phase3-steer-e2e.webm
    webui-full-e2e.webm
    webui-{test-name}.webm
  screenshots/
    webui-two-pane.png
    webui-settings-persist.png
```

These are committed to the repo so any developer can view them.

---

## Hermes-Agent Plugin API Quick Reference

### Hooks
```python
ctx.register_hook("pre_gateway_dispatch", on_incoming)  # refine
ctx.register_hook("pre_llm_call", on_before_llm)         # inject steering
ctx.register_hook("post_llm_call", on_after_llm)         # distill
ctx.register_hook("on_session_start", on_session_start)   # init state
ctx.register_hook("on_session_end", on_session_end)     # cleanup
```

### Steering (existing mechanism)
```python
# Non-interrupting: agent continues, gets correction in next tool result
agent.steer("Stay focused on the fix")
# → Next tool result gets "User guidance: Stay focused on the fix"

# Interrupting: use only when we want immediate behavior change
ctx.inject_message("Stop", role="user")
```

### Audio Config
```yaml
# ~/.hermes/config.yaml
intermediary:
  enabled: true
  features:
    refine: true
    distill: true
    steer: true
  audio:
    backend: ten    # ten | pipecat | livekit | mock | none
    barge_in: true
```

---

## Files Created / Modified

### New Files (this repo)
```
intermediary-agent/
  README.md
  PLAN.md
  ROADMAP.md
  INTEGRATION.md
  intermediary/
    __init__.py
    plugin.yaml
    config.py
    state.py
    refine.py
    distill.py
    steer.py
    hooks.py
  audio/
    __init__.py
    base.py
    ten_backend.py
    pipecat_backend.py
    livekit_backend.py
  surfaces/
    __init__.py
    discord_surface.py
    webui_surface.py
    cli_surface.py
  prompts/
    refine_system.md
    distill_system.md
    steer_system.md
  webui_extension/
    intermediary.css
    intermediary.js
    manifest.json
  tests/
    test_refine.py
    test_distill.py
    test_steer.py
    test_hooks.py
    test_audio_base.py
    conftest.py              # Playwright config with video recording
  test-evidence/
    videos/
    screenshots/
```

### Modified Files (in hermes-agent)
```
hermes-agent/
  hermes_cli/plugins.py              # Add intermediary hooks + ctx.steer_agent()
  hermes_cli/config.py               # Add intermediary: config section
  gateway/platforms/discord.py       # Wire audio backend to VoiceReceiver (minimal)
```

### Modified Files (in hermes-webui)
```
hermes-webui/
  static/extension_settings.js       # Register intermediary extension
  static/boot.js                     # Intercept STT/text, refine
  static/ui.js                       # Two-pane composer + sidebar
  static/panels.js                   # Intermediary preferences
  static/index.html                  # Composer markup + sidebar
  api/extensions.py                  # SSE endpoint
  api/upload.py                      # Refine after STT
```

---

## Skill Alignment

This repo incorporates knowledge from these skills:

| Skill | What We Took |
|-------|-------------|
| `agent-pipeline-intermediary` | Architecture pattern, hook signatures, `IntermediaryState` dataclass, prompt templates, surface adapter patterns |
| `deep-think` | Mandatory empirical validation (not just code-reading), testing with real system |
| `Playwright` | Video recording of frontend/voice tests for human-verifiable evidence |

---

## Definition of Done

A phase is complete when:
- [ ] All milestones checked off
- [ ] Tests passing
- [ ] Linting clean
- [ ] Manual E2E test passed (success criteria above)
- [ ] Video evidence recorded for each platform
- [ ] Documentation updated
- [ ] No regressions in existing hermes-agent/hermes-webui tests

---

## External Dependencies

| Dependency | Repo | Status | Use Case |
|---|---|---|---|
| Plugin system | [hermes-agent](https://github.com/NousResearch/hermes-agent) | ✅ Existing | PluginContext, hooks, agent.steer() |
| Voice IO | [hermes-agent](https://github.com/NousResearch/hermes-agent) | ✅ Existing | VoiceReceiver |
| STT | [hermes-agent](https://github.com/NousResearch/hermes-agent) | ✅ Existing | transcription_tools |
| WebUI Extensions | [hermes-webui](https://github.com/ChonSong/hermes-webui) | ✅ Existing | extension_settings.js |
| Discord API | [discord.py](https://github.com/Rapptz/discord.py) | ✅ Existing | VC + edit_message |
| Observability | [Langfuse](https://github.com/langfuse/langfuse) | ✅ Existing | (optional) |
| Turn Detection | [TEN](https://github.com/ten-framework/ten-framework) | 🆕 New | Full-duplex turn-taking |
| VAD | [TEN](https://huggingface.co/TEN-framework/ten-vad) | 🆕 New | Voice activity detection |
| Pipeline | [Pipecat](https://github.com/pipecat-ai/pipecat) | 🆕 New | Concurrent STT+LLM+TTS |
| Transport | [LiveKit](https://github.com/livekit/agents) | 🆕 New | Browser WebRTC voice |
| Testing | [Playwright](https://playwright.dev/) | 🆕 New | Video evidence for frontend/voice |
