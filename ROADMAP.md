# Intermediary Agent — Roadmap

## Phase 0: Foundation (Current)

- [x] Create repo structure
- [x] Write PLAN.md (architecture, components, integration points)
- [x] Write ROADMAP.md (this file)
- [x] Write INTEGRATION.md (file paths, function signatures)
- [ ] Set up development environment (venv, dependencies)
- [ ] Create test scaffolding

### Phase 0 Success Criteria (human-verifiable)

- [ ] Repo has README that a new developer can read in 5 minutes and understand what we're building
- [ ] PLAN.md describes every component with a diagram
- [ ] ROADMAP.md has milestones for at least Phase 1-4
- [ ] INTEGRATION.md has exact file paths for hermes-agent and hermes-webui
- [ ] Repository is public on GitHub

---

## Phase 1: Hermes-Agent Plugin (Text-Only, Discord)

**Goal**: Working intermediary as a hermes-agent plugin. Text input only. Discord surface.

### Milestone 1.1: Plugin Scaffold
- [ ] `intermediary/__init__.py` — register() entry point
- [ ] `intermediary/plugin.yaml` — manifest
- [ ] `intermediary/config.py` — config schema
- [ ] `intermediary/state.py` — IntermediaryState dataclass
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
- [ ] `intermediary/refine.py` — single LLM call to refine input
- [ ] `prompts/refine_system.md` — refinement prompt template
- [ ] Conversation context / pronoun resolution
- [ ] Unit tests with mocked LLM responses

**Files**:
```
intermediary/
  refine.py
prompts/
  refine_system.md
tests/
  test_refine.py
```

### Milestone 1.3: Hook Integration
- [ ] `intermediary/hooks.py` — register pre_gateway_dispatch hook
- [ ] Wire: incoming message → refine → send refined to agent
- [ ] Store original + refined in state
- [ ] Integration test with hermes-agent mock

**Files**:
```
intermediary/
  hooks.py
tests/
  test_hooks_integration.py
```

### Milestone 1.4: Discord Surface
- [ ] `surfaces/discord_surface.py` — send_refined, start_progress, update_progress
- [ ] Edit-message pattern for progress updates
- [ ] Rate-limited edits (500ms interval)
- [ ] Final summary replacement
- [ ] Mock Discord channel tests

**Files**:
```
surfaces/
  __init__.py
  discord_surface.py
tests/
  test_discord_surface.py
```

### Milestone 1.5: Distill Engine
- [ ] `intermediary/distill.py` — buffer agent output, produce progress updates
- [ ] `prompts/distill_system.md` — distillation prompt template
- [ ] Streaming token buffer
- [ ] Milestone detection (topic shifts, completions)
- [ ] Unit tests with mock streaming

**Files**:
```
intermediary/
  distill.py
prompts/
  distill_system.md
tests/
  test_distill.py
```

### Milestone 1.6: End-to-End Text Test
- [ ] Run intermediary with real hermes-agent (text-only, Discord DM)
- [ ] Verify: raw text → refined → progress updates → final summary
- [ ] Tune prompts based on real outputs
- [ ] Latency measurements

### Phase 1 Success Criteria (human-verifiable)

**Test procedure**: Enable intermediary in a real Discord DM with the bot. Send text messages. Watch the bot response.

- [ ] **Refine displays**: Bot sends the refined version of your messy text before its main response. (e.g., you send "um the docker thing?" → bot shows "Refined: Debug the Docker permission error")
- [ ] **Edit pattern is working**: Bot edits its original message to update progress, not spam new messages. Send /reset, then send a prompt that elicits a long response. The bot's progress message should be EDITED in place.
- [ ] **Progress updates are concise**: A long agent response (< 500 tokens) generates ≤ 3 progress updates from intermediary.
- [ ] **Final summary appears**: After agent finishes, intermediary shows a single-line summary of the result.
- [ ] **Latency acceptable**: Refined text appears within 1 second of hitting Enter.
- [ ] **No-agent impact**: Disabling the intermediary plugin doesn't break normal bot behavior. Chat still works.
- [ ] **Pronoun resolution works**: After discussing Docker in a conversation, sending "ok what about that?" → refined text correctly references "the Docker permission error".
- [ ] **Rate limit safety**: Rapid-fire sending 5 messages in a row doesn't crash the intermediary or cause Discord API 429s.

---

## Phase 2: Voice Input (Discord)

**Goal**: Voice input via existing hermes-agent VoiceReceiver + STT.

### Milestone 2.1: Voice-to-Refined Pipeline
- [ ] Bridge VoiceReceiver output → intermediary refine engine
- [ ] Send refined transcript (not raw) to agent
- [ ] Surface: "Transcribing..." → "Refined: ..." → "Sending..."

### Milestone 2.2: Continuous Refinement
- [ ] For long utterances, refine incrementally (interim results)
- [ ] Show interim refined text while user is still speaking
- [ ] Final refinement when silence detected

### Phase 2 Success Criteria (human-verifiable)

**Test procedure**: Join a Discord voice channel. Speak to the bot. Watch text channel updates.

- [ ] **Voice transcribes**: Speaking in VC causes the bot to transcribe your speech and show the raw transcript in the text channel
- [ ] **Refinement is visible**: The refined transcript appears in the text channel before the bot's response
- [ ] **Interim refinement**: While you're still speaking, the bot shows refining text updates (so you know it's working)
- [ ] **No voice when agent speaks**: Bot pauses your mic while playing its TTS reply (if applicable), preventing self-hearing
- [ ] **Silence detection works**: Bot auto-sends after you stop speaking (1.5s silence), doesn't wait forever
- [ ] **Empty speech handled**: If you make noise but say nothing, bot shows "No speech detected" instead of sending garbage

---

## Phase 3: Steering Engine

**Goal**: Detect and correct agent drift mid-stream.

### Milestone 3.1: Drift Detection
- [ ] `intermediary/steer.py` — compare streaming output to user_intent
- [ ] `prompts/steer_system.md` — drift detection prompt
- [ ] Confidence scoring (don't intervene too early)

### Milestone 3.2: Injection Mechanism
- [ ] `ctx.inject_message()` to redirect mid-turn
- [ ] Surface: "Redirecting: stay focused on..."
- [ ] Track injection history (avoid repeated steering on same topic)

### Milestone 3.3: Steering Tuning
- [ ] Don't over-steer (let agent explore productively)
- [ ] Don't under-steer (catch real drift early)
- [ ] A/B test drift_confidence thresholds

### Phase 3 Success Criteria (human-verifiable)

**Test procedure**: Deliberately ask the bot a question that might elicit off-topic information. Example: "how do i fix the docker permission error?" when the bot historically explains docker architecture.

- [ ] **Steering triggers on drift**: When the bot starts going off-topic, the intermediary injects a correction message (visible in log/channel)
- [ ] **Progress shows redirection**: Intermediary updates its progress message to mention redirection ("Redirecting, stay focused on the fix...")
- [ ] **No over-steering**: Bot exploring related-but-useful context (e.g., checking logs to find the cause) doesn't trigger steering
- [ ] **Agent corrects course**: After steering injection, the agent gets back to the user's intent
- [ ] **Injection is single, not spammy**: Max one steering injection per exchange. No repeated corrections for the same topic

---

## Phase 4: WebUI Extension

**Goal**: Two-pane composer + intermediary sidebar in hermes-webui.

### Milestone 4.1: Extension Scaffold
- [ ] `webui_extension/` — extension files (manifest, HTML, CSS, JS)
- [ ] Register with hermes-webui extension system
- [ ] SSE connection to intermediary API

### Milestone 4.2: Two-Pane Composer
- [ ] Raw transcript pane (top, grayed)
- [ ] Refined pane bottom, editable)
- [ ] Real-time update as user types/speaks

### Milestone 4.3: Intermediary Sidebar
- [ ] Progress updates during agent response
- [ ] Steering notifications
- [ ] Final summary card

### Milestone 4.4: Settings Panel
- [ ] Toggle refine/distill/steer independently
- [ ] Model selection per engine
- [ ] Update interval controls
- [ ] Auto-send vs manual approve

### Phase 4 Success Criteria (human-verifiable)

**Test procedure**: Open WebUI in browser. Type in the intermediary pane. Use mic for voice.

- [ ] **Installation**: `hermes webui extensions install intermediary` installs the extension. Or it appears in the Extensions gallery.
- [ ] **Two-pane visible**: Composer has raw + refined panes, clearly labeled, not overlapping
- [ ] **Real-time refinement**: As you type "um the docker thing?", refined panes shows "Debug the Docker permission error" within 500ms
- [ ] **Editable refined**: You can click into the refined pane and edit before hitting Enter. Sending uses YOUR edited text, not the original refinement
- [ ] **Sidebar shows progress**: During a long bot response, the sidebar shows "Looking into it..." → "Found 3 issues" → "Here's the main one"
- [ ] **Voice button triggers intermediary**: Clicking mic → STT → intermediary refines → both panes update. Not just direct send.
- [ ] **Settings persist**: Toggle "refine" off → reload → still off. (localStorage or settings API)
- [ ] **Mobile works**: Composer doesn't break on narrow panes; panes stack vertically or collapse

---

## Phase 5: CLI/TUI Surface

**Goal**: Status line + refined display in terminal.

### Milestone 5.1: CLI Surface
- [ ] `surfaces/cli_surface.py`
- [ ] Status bar updates (looking into it... / found it...)
- [ ] Refined transcript display before send

### Phase 5 Success Criteria (human-verifiable)

**Test procedure**: Run `hermes` in terminal. Type messages.

- [ ] **Status line shows progress**: During response, a status/display line shows intermediary updates ("Looking into it..." → "Found it")
- [ ] **Refined prompt displays**: After typing, refined prompt shown (with [y/n] or similar to confirm send)
- [ ] **Color coding**: Success/failure visually distinct in terminal (green ✓, red ✗, yellow ⟳)

---

## Phase 6: Hardening & Polish

**Goal**: Production-ready.

### Milestone 6.1: Error Handling
- [ ] LLM call failures → graceful degradation (pass-through)
- [ ] Rate limit handling
- [ ] Timeout handling

### Milestone 6.2: Observability
- [ ] Langfuse tracing integration (reuse existing langfuse plugin)
- [ ] Per-exchange latency telemetry
- [ ] Drift event logging

### Milestone 6.3: Documentation
- [ ] User guide (how to enable, how to use)
- [ ] Developer guide (how it works, how to extend)
- [ ] Configuration reference

### Phase 6 Success Criteria (human-verifiable)

- [ ] **Offline recovery**: If intermediary's LLM provider is unreachable, the conversation still works normally (just no refinement/distillation/stats) — logs show "intermediary unavailable, pass-through mode"
- [ ] **Config validation**: Setting `intermediary.enabled: yes` or `intermediary.features.refine: 1` doesn't crash; human-friendly warning shown
- [ ] **Self-diagnostic**: `hermes intermediary doctor` reports: plugin loaded? config valid? LLM provider reachable? Discord surface ready?
- [ ] **Log volume reasonable**: A single exchange generates < 20 intermediary log lines at INFO level
- [ ] **No PII in logs**: User messages are not logged verbatim at INFO level (only at DEBUG + redacted)

---

## Phase 7: Research & Advanced Features

### Milestone 7.1: Multi-Turn Refinement
- [ ] Use conversation history to resolve references
- [ ] Cross-turn pronoun tracking

### Milestones 7.2: Proactive Suggestions
- [ ] Intermediary suggests follow-up questions
- [ ] Pre-fetch likely needed context

### Milestone 7.3: User Model
- [ ] Learn user's preferred communication style
- [ ] Adapt distillation level per user

### Phase 7 Success Criteria (human-verifiable)

- [ ] **Reference resolution**: After 5+ turns discussing multiple topics, "fix that" correctly references the most recent topic, not the oldest
- [ ] **Follow-up suggestions**: After a bot response finishes, intermediary suggests 2-3 natural follow-ups (visible as clickable chips or text)
- [ ] **Style adaptation**: After 3+ sessions, intermediary refines in a way the user finds natural (subjective but verifiable via user feedback)

---

## Definition of Done

A phase is complete when:
- [ ] All milestones checked off
- [ ] Tests passing (`pytest tests/ -q`)
- [ ] Linting clean (`ruff check intermediary/`)
- [ ] Manual E2E test passed on all supported platforms (success criteria above)
- [ ] Documentation updated (README, PLAN, INTEGRATION reflect current state)
- [ ] No regressions in existing hermes-agent/hermes-webui tests
- [ ] README success criteria section updated to reflect current phase

---

## External Dependencies

| Dependency | Repo | Status | Notes |
|---|---|---|---|
| Plugin system | [hermes-agent](https://github.com/NousResearch/hermes-agent) | ✅ Existing | `PluginContext`, hooks, `VALID_HOOKS` |
| Voice IO | [hermes-agent](https://github.com/NousResearch/hermes-agent) | ✅ Existing | `VoiceReceiver` in `gateway/platforms/discord.py` |
| STT | [hermes-agent](https://github.com/NousResearch/hermes-agent) | ✅ Existing | `tools/transcription_tools.py` |
| WebUI Extensions | [hermes-webui](https://github.com/ChonSong/hermes-webui) | ✅ Existing | `static/extension_settings.js`, `api/extensions.py` |
| Discord API | [discord.py](https://github.com/Rapptz/discord.py) | ✅ Existing | `VoiceClient`, `edit_message` |
| Observability | [Langfuse](https://github.com/langfuse/langfuse) | ✅ Existing | `plugins/observability/langfuse/` |

## Hermes-Agent Plugin Development Workflow

### Dev Install
```bash
# In hermes-agent checkout
pip install -e path/to/intermediary-agent
```

### Enable Plugin
```yaml
# ~/.hermes/config.yaml
plugins:
  enabled:
    - intermediary
```

### Test with Discord
```bash
# Terminal 1: Start hermes gateway with intermediary
hermes gateway

# Terminal 2: Watch logs
tail -f ~/.hermes/logs/gateway.log | grep -i intermediary
```

## Key Hermes-Agent Code Paths (for reference)

| Purpose | File | Symbol |
|---|---|---|
| Plugin registration | `hermes_cli/plugins.py` | `PluginContext.register()` |
| Hook invocation | `hermes_cli/plugins.py` | `invoke_hook(name, **kwargs)` |
| Pre-dispatch hook | `hermes_cli/plugins.py` | `VALID_HOOKS` includes `pre_gateway_dispatch` |
| Message injection | `hermes_cli/plugins.py` | `ctx.inject_message(content, role)` |
| Discord adapter | `gateway/platforms/discord.py` | `class DiscordAdapter` |
| Voice receiver | `gateway/platforms/discord.py` | `class VoiceReceiver` |
| Discord edit | `gateway/platforms/discord.py` | `async def edit_message()` |
| Voice STT | `tools/transcription_tools.py` | `transcribe_audio(file_path)` |
| Voice mode | `tools/voice_mode.py` | Voice mode state machine |
| Config schema | `hermes_cli/config.py` | `load_config()`, `cfg_get()` |

## Key Hermes-WebUI Code Paths (for reference)

| Purpose | File | What to Add |
|---|---|---|
| Extension hookup | `static/extension_settings.js` | Register intermediary extension |
| Composer UI | `static/index.html` | Two-pane composer markup |
| Voice pipeline | `static/boot.js` | Intermediary intercept after STT |
| Settings UI | `static/panels.js` | Intermediary preferences |
| Backend API | `api/extensions.py` | `/api/intermediary/stream` SSE |
| TTS registration | `static/boot.js` | (already exists, reuse pattern for intermediary) |
