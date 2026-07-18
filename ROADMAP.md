# Intermediary Agent — Roadmap

## Phase 0: Foundation (Current)

- [x] Create repo structure
- [x] Write PLAN.md (architecture, components, integration points)
- [x] Write ROADMAP.md (this file)
- [x] Write INTEGRATION.md (file paths, function signatures)
- [x] Research existing /steer mechanism
- [x] Research full-duplex audio frameworks (TEN, Pipecat, LiveKit)
- [ ] Set up development environment (venv, dependencies)
- [ ] Create test scaffolding

### Phase 0 Success Criteria (human-verifiable)

- [ ] Repo README explains what we are building
- [ ] PLAN.md has architecture diagram, component design, prompt templates
- [ ] ROADMAP.md has phases with human-verifiable success criteria
- [ ] Steering plan hooks into existing `agent.steer()` — not reinvented
- [ ] Audio is pluggable sublayer (TEN/Pipecat/LiveKit) — not bolted on later
- [ ] INTEGRATION.md has exact file paths for hermes-agent and hermes-webui

---

## Phase 1: Hermes-Agent Plugin (Text Only, Discord)

**Goal**: Working intermediary as a hermes-agent plugin. Text input only. Discord surface. No audio.

### Milestone 1.1: Plugin Scaffold
- [ ] `intermediary/__init__.py` — register() entry point
- [ ] `intermediary/plugin.yaml` — manifest
- [ ] `intermediary/config.py` — config schema
- [ ] `intermediary/state.py` — IntermediaryState dataclass
- [ ] Unit tests for state management

### Milestone 1.2: Refine Engine
- [ ] `intermediary/refine.py` — LLM call to refine input
- [ ] `prompts/refine_system.md` — refinement prompt template
- [ ] Conversation context + pronoun resolution
- [ ] Unit tests with mocked LLM

### Milestone 1.3: Hook Integration (pre_gateway_dispatch)
- [ ] `intermediary/hooks.py` — register pre_gateway_dispatch hook
- [ ] Wire: incoming message → refine → replace event.text → send refined to agent
- [ ] Store original + refined in state
- [ ] Integration test with hermes-agent mock

### Milestone 1.4: Discord Surface
- [ ] `surfaces/discord_surface.py` — edit-message pattern
- [ ] send_refined(), start_progress(), update_progress(), send_final()
- [ ] Rate-limited edits (500ms interval)
- [ ] Mock Discord channel tests

### Milestone 1.5: Distill Engine
- [ ] `intermediary/distill.py` — buffer token stream, produce progress updates
- [ ] `prompts/distill_system.md` — distillation prompt template
- [ ] Milestone detection (topic shifts, completions)
- [ ] Unit tests with mock streaming

### Milestone 1.6: Steer Engine (using agent.steer())
- [ ] `intermediary/steer.py` — detect drift, call `agent.steer()` to inject correction
- [ ] `prompts/steer_system.md` — drift detection prompt
- [ ] CONFIRMED: steering uses existing `agent.steer()` — non-interrupting, injected into next tool result
- [ ] Rate-limited: max 1 steer injection per exchange
- [ ] Mock test: verify agent receives steer text after tool call

### Milestone 1.7: End-to-End Text Test
- [ ] Run with real hermes-agent in Discord DM
- [ ] Verify full flow: raw → refined → agent response → distill → final summary
- [ ] Verify drift: when agent goes off-topic, it corrects without interruption

### Phase 1 Success Criteria (human-verifiable)

**Test procedure**: Enable intermediary in a real Discord DM with the bot. Send text messages. Watch the bot response.

- [ ] **Refine displays**: Bot sends the refined version of your messy text before its main response
- [ ] **Edit pattern**: Bot edits its original message to update progress, not spam new messages
- [ ] **Progress updates concise**: A long agent response (<500 tokens) generates ≤3 progress updates
- [ ] **Final summary appears**: After agent finishes, intermediary shows a single-line summary
- [ ] **Latency**: Refined text appears within 1 second of hitting Enter
- [ ] **No-agent fallback**: Disabling intermediary plugin doesn't break normal bot
- [ ] **Pronoun resolution**: After discussing Docker, sending "ok what about that?" references "Docker permission error"
- [ ] **Steer non-interrupting**: When agent goes off-topic, it continues working but receives correction. User does NOT see an interruption — agent just adjusts course
- [ ] **Steer visible in logs**: Gateway log shows `agent.steer()` called with correction text

---

## Phase 2: Audio Sublayer + Voice Input

**Goal**: Plug in audio backends. Voice input via Discord voice channel.

### Milestone 2.1: Audio Backend Abstraction
- [ ] `audio/base.py` — AudioBackend ABC (start_listening, speak, stop_speaking, detect_turn)
- [ ] `audio/ten_backend.py` — TEN Turn Detection integration for turn-taking
- [ ] Abstract barge-in: user speaks → agent stops talking
- [ ] Mock audio backend for testing

### Milestone 2.2: Voice-to-Refined Pipeline
- [ ] Bridge VoiceReceiver output → intermediary refine engine
- [ ] STT → raw transcript → refine → send refined to agent
- [ ] Surface: "Transcribing..." → "Refined: ..." → "Sending..."
- [ ] Interim refinement while user still speaking

### Milestone 2.3: Barge-in
- [ ] When user speaks while agent is talking: stop TTS immediately
- [ ] Back to listening without losing context
- [ ] Surface: "Interrupted. Listening..."
- [ ] TEN Turn Detection for determining when user is done speaking

### Milestone 2.4: Audio Backend Swap Test
- [ ] Mock backend → TEN backend: swap via config change, no code changes
- [ ] Verify all backends implement the same interface
- [ ] Latency comparison: mock vs TEN vs (future) Pipecat

### Phase 2 Success Criteria (human-verifiable)

**Test procedure**: Join Discord voice channel. Speak to the bot. Watch text channel updates.

- [ ] **Voice transcribes**: Speaking in VC causes bot to transcribe and show raw transcript in text channel
- [ ] **Refinement visible**: Refined transcript appears before bot's response
- [ ] **Barge-in works**: Start speaking while bot is replying → bot stops talking within 200ms
- [ ] **Turn detection**: Bot knows when you're done speaking, doesn't cut you off mid-sentence
- [ ] **No self-hearing**: Bot's own TTS output doesn't trigger its own STT
- [ ] **Audio backend swap**: Config change `audio.backend: ten` → works. `audio.backend: mock` → works. Same intermediary logic.

---

## Phase 3: Pipecat Integration (Concurrent Pipeline)

**Goal**: Pipecat for concurrent STT+LLM+TTS. Enables true full-duplex — agent can start responding before user finishes speaking.

### Milestone 3.1: Pipecat Backend
- [ ] `audio/pipecat_backend.py` — Pipecat pipeline integration
- [ ] ParallelPipeline: STT, LLM, TTS running concurrently
- [ ] Barge-in via Pipecat's built-in interruption handling

### Milestone 3.2: Concurrent Input/Output
- [ ] Agent starts responding while user finishes speaking (streaming STT → LLM)
- [ ] TTS starts before full response is generated
- [ ] If user interrupts: stop TTS, flush LLM buffer, return to listening

### Milestone 3.3: Latency Optimization
- [ ] Measure: user stops speaking → agent starts responding
- [ ] Target: <500ms (the "full-duplex threshold")
- [ ] Compare: TEN backend vs Pipecat backend latency

### Phase 3 Success Criteria (human-verifiable)

- [ ] **Concurrent**: Start responding before user finishes speaking — you hear the agent begin while you're still talking
- [ ] **Sub-second latency**: Agent starts responding <500ms after you stop speaking
- [ ] **No echo**: Agent doesn't react to its own voice output
- [ ] **Interrupt召 works mid-sentence**: Agent cuts itself off when you start speaking

---

## Phase 4: WebUI Extension

**Goal**: Two-pane composer + intermediary sidebar + browser voice.

### Milestone 4.1: Extension Scaffold
- [ ] `webui_extension/` — manifest, CSS, JS
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

### Milestone 4.4: WebUI Voice (LiveKit)
- [ ] LiveKit audio backend for browser voice
- [ ] Connect to intermediary audio sublayer
- [ ] Two-way voice: speak in browser, hear agent response

### Phase 4 Success Criteria (human-verifiable)

- [ ] **Two-pane visible**: Composer has raw + refined panes
- [ ] **Real-time refinement**: As you type "um the docker thing?", refined pane shows "Debug the Docker permission error" within 500ms
- [ ] **Editable refined**: Click into refined pane, edit, send YOUR text
- [ ] **Sidebar progress**: During long agent response, sidebar shows "Looking into it..." → "Found 3 issues" → "Here's the main one"
- [ ] **Browser voice**: Click mic in WebUI → speak → agent responds by voice
- [ ] **Mobile works**: Composer doesn't break on narrow screens

---

## Phase 5: CLI/TUI Surface

**Goal**: Terminal interface.

### Milestone 5.1: CLI Surface
- [ ] `surfaces/cli_surface.py` — status line updates
- [ ] Refined transcript confirmation before send

### Phase 5 Success Criteria (human-verifiable)

- [ ] **Status line**: During agent response, status updates like Discord pane
- [ ] **Refined confirmation**: Shows refined prompt, [y/n] to send
- [ ] **Color coding**: Green ✓, red ✗, yellow ⟳ for progress states

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
- [ ] Developer guide
- [ ] Configuration reference

### Phase 6 Success Criteria (human-verifiable)

- [ ] **Offline recovery**: Intermediary's LLM provider unreachable → conversation still works (no refinement, no distill, no steer), logs show "pass-through mode"
- [ ] **Self-diagnostic**: `hermes intermediary doctor` reports: plugin loaded? config valid? LLM reachable? Audio backend ready?
- [ ] **No PII in logs**: User messages not logged at INFO level (only DEBUG + redacted)

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

### Phase 7 Success Criteria (human-verifiable)

- [ ] **Reference resolution**: After 5+ turns discussing multiple topics, "fix that" correctly references the most recent topic
- [ ] **Follow-up suggestions**: After agent response finishes, intermediary suggests 2-3 natural follow-ups
- [ ] **Style adaptation**: After 3+ sessions, intermediary refines in a way the user finds natural

---

## Definition of Done

A phase is complete when:
- [ ] All milestones checked off
- [ ] Tests passing
- [ ] Linting clean
- [ ] Manual E2E test passed on all supported platforms (success criteria above)
- [ ] Documentation updated
- [ ] No regressions in existing hermes-agent/hermes-webui tests

---

## External Dependencies

| Dependency | Repo | Status | Use Case |
|---|---|---|---|
| Plugin system | [hermes-agent](https://github.com/NousResearch/hermes-agent) | ✅ Existing | PluginContext, hooks, agent.steer() |
| Voice IO | [hermes-agent](https://github.com/NousResearch/hermes-agent) | ✅ Existing | VoiceReceiver |
| STT | [hermes-agent](https://github.com/NousResearch/hermes-agent) | ✅ Existing | transcription_tools |
| WebUI Extensions | [hermes-webui](https://github.com/ChonSong/hermes-webui) | ✅ Existing | extension_settings.js, extensions.py |
| Discord API | [discord.py](https://github.com/Rapptz/discord.py) | ✅ Existing | VC + edit_message |
| Observability | [Langfuse](https://github.com/langfuse/langfuse) | ✅ Existing | (optional) |
| Turn Detection | [TEN](https://github.com/ten-framework/ten-framework) | 🆕 New | Full-duplex turn-taking |
| VAD | [TEN](https://huggingface.co/TEN-framework/ten-vad) | 🆕 New | Voice activity detection |
| Pipeline | [Pipecat](https://github.com/pipecat-ai/pipecat) | 🆕 New | Concurrent STT+LLM+TTS |
| Transport | [LiveKit](https://github.com/livekit/agents) | 🆕 New | Browser WebRTC voice |

---

## Hermes-Agent Plugin API Quick Reference

### Hooks (lifecycle callbacks)

```python
def register_hook(self, name: str, callback: Callable) -> None: ...

# Existing hooks we use:
ctx.register_hook("pre_gateway_dispatch", on_incoming)
ctx.register_hook("on_session_start", on_session_start)
ctx.register_hook("on_session_end", on_session_end)

# New hooks we add:
ctx.register_hook("intermediary_refined", on_refined)
ctx.register_hook("intermediary_distilled", on_distilled)
ctx.register_hook("intermediary_steered", on_steered)
```

### Context Injection (existing, we use this)

```python
ctx.inject_message("Stay focused", role="user")
# → INTERRUPTS the agent and injects the message
# → For CLI mode: cli._interrupt_queue.put(msg)
# → For gateway mode: interrupts pending agent run
```

### Steer Injection (existing, WE USE THIS FOR DRIFT)

```python
# In PluginContext, add:
ctx.steer_agent(session_id, "Stay focused on the fix")
# → Calls agent.steer(text) — NON-interrupting
# → Text is appended to next tool result as "User guidance: ..."
# → Agent sees correction inline, adjusts without interruption
```

### New: Audio Backend Config

```yaml
# ~/.hermes/config.yaml
intermediary:
  enabled: true
  features:
    refine: true
    distill: true
    steer: true
  audio:
    backend: ten    # ten | pipecat | livekit | discord | none
    barge_in: true
    turn_detection: true
  models:
    refine: "default"
    distill: "default"
    steer: "default"
  thresholds:
    drift_confidence: 0.7
    silence_ms: 1800
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
```

### Modified Files (in hermes-agent / hermes-webui)

```
hermes-agent/
  hermes_cli/plugins.py              # Add intermediary hooks + ctx.steer_agent()
  hermes_cli/config.py               # Add intermediary: config section
  gateway/platforms/discord.py       # Wire audio backend to VoiceReceiver (minimal)

hermes-webui/
  static/extension_settings.js       # Register intermediary extension
  static/boot.js                     # Intercept STT/text, refine
  static/ui.js                       # Two-pane composer + sidebar
  static/panels.js                   # Intermediary preferences
  static/index.html                  # Composer markup + sidebar
  api/extensions.py                  # SSE endpoint
  api/upload.py                      # Refine after STT
```
