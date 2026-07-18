# Intermediary Agent — Roadmap

## Phase 0: Foundation (Current)

- [x] Create repo structure
- [x] Write PLAN.md (architecture, components, integration points)
- [x] Write ROADMAP.md (this file)
- [ ] Set up development environment (venv, dependencies)
- [ ] Create test scaffolding

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

## Phase 5: CLI/TUI Surface

**Goal**: Status line + refined display in terminal.

### Milestone 5.1: CLI Surface
- [ ] `surfaces/cli_surface.py`
- [ ] Status bar updates (looking into it... / found it...)
- [ ] Refined transcript display before send

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

---

## Definition of Done

A phase is complete when:
- [ ] All milestones checked off
- [ ] Tests passing (`pytest tests/ -q`)
- [ ] Linting clean (`ruff check intermediary/`)
- [ ] Manual E2E test passed on all supported platforms
- [ ] Documentation updated
- [ ] No regressions in existing hermes-agent/hermes-webui tests

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
