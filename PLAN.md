# Intermediary Agent — Complete Plan

## Vision

A semantic supervisor that sits between the human and Hermes. It **refines** messy input, **distills** verbose output into natural progress updates, and **steers** the agent back on track — all visible and editable in real time. No TTS required. Works across WebUI, Discord, and CLI.

## Problem Statement

Current Hermes voice/text interaction has three friction points:

1. **Input friction**: Users speak in fragments — "um so like the docker thing I was talking about earlier?" — but agents need structured prompts
2. **Output friction**: Hermes responds in thorough essays when users want concise progress updates
3. **Drift friction**: Agents go off-topic mid-response and there's no mechanism to redirect without restarting

Existing frameworks (Pipecat, LiveKit, TEN) solve *voice IO* but not *semantic supervision*. They assume output is audio. We need a text-based intermediary that manages meaning, not waveforms.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        HERMES AGENT                                │
│                                                                     │
│  ┌─────────────┐    ┌──────────────────────────────────────────┐   │
│  │   Platform   │    │           INTERMEDIARY PLUGIN             │   │
│  │   Adapters   │    │                                          │   │
│  │              │    │  ┌─────────┐  ┌──────────┐  ┌────────┐ │   │
│  │  ┌────────┐  │    │  │ Refine  │  │ Distill  │  │ Steer  │ │   │
│  │  │Discord │──┼────┼─>│ Engine  │─>│ Engine   │─>│ Engine │ │   │
│  │  └────────┘  │    │  └─────────┘  └──────────┘  └────────┘ │   │
│  │  ┌────────┐  │    │       │              │            │      │   │
│  │  │ WebUI  │──┼────┤       │              │            │      │   │
│  │  └────────┘  │    │  ┌────┴──────────────┴────────────┴───┐ │   │
│  │  ┌────────┐  │    │  │         State Manager              │ │   │
│  │  │ CLI    │──┼────┤  │  • Intent tracker (pronouns)       │ │   │
│  │  └────────┘  │    │  │  • Conversation context            │ │   │
│  │              │    │  │  • Drift detector                  │ │   │
│  └─────────────┘    │  └────────────────────────────────────┘ │   │
│                       └──────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Hermes Core (existing)                     │   │
│  │  • LLM pipeline  • Tool dispatch  • Session management       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Plugin Core (`intermediary/`)

**`__init__.py`** — Plugin entry point. Registers all hooks via `PluginContext`.

**`config.py`** — Configuration schema and validation.

```yaml
intermediary:
  enabled: true
  features:
    refine: true      # Enable input refinement
    distill: true     # Enable output distillation
    steer: true       # Enable mid-turn steering
  models:
    refine: "default"      # Model for refinement (fast, cheap)
    distill: "default"     # Model for distillation
    steer: "default"       # Model for steering decisions
  thresholds:
    drift_confidence: 0.7  # How sure before injecting steer
    silence_ms: 1800       # For voice input
  platforms:
    discord:
      edit_interval_ms: 500    # How often to edit progress message
      max_update_length: 1800  # Discord message limit headroom
    webui:
      stream_mode: "sentence"  # "token" | "sentence" | "manual"
    cli:
      spinner: true
```

**`state.py`** — Conversational state management.

```python
@dataclass
class IntermediaryState:
    session_id: str
    user_intent: str           # Resolved user intent (pronouns expanded)
    intent_history: list[str]  # Previous intents (for context)
    drift_baseline: str       # What the user asked for
    current_topic: str        # What the agent is currently on
    message_queue: asyncio.Queue  # Pending intermediary messages
```

**`refine.py`** — Input refinement engine.

- Takes raw transcript + conversation context
- Resolves pronouns ("that thing", "what we discussed") using intent_history
- Outputs structured, actionable prompt
- Quick: small model, single LLM call

**`distill.py`** — Output distillation engine.

- Buffers streaming tokens from Hermes
- Detects progress milestones (shifts in topic, completion of subtasks)
- Generates natural progress updates
- Runs concurrently with agent output (non-blocking)

**`steer.py`** — Drift detection and correction.

- Receives streaming output, compares against user_intent
- If drift_confidence > threshold, drafts correction injection
- Uses `inject_message()` to redirect without stopping agent
- Preserves agent's work (doesn't restart, just nudges)

### 2. Prompt Engineering (`prompts/`)

**`refine_system.md`**
```
You are an input refinement engine. Your job is to restructure messy spoken
or typed input into a clear, actionable prompt for an AI agent.

Rules:
1. Preserve the user's original intent exactly
2. Resolve pronouns using conversation context
3. Expand vague references ("that thing", "the error") to specific terms
4. Structure as: [Action] + [Context] + [Constraints]
5. If the user asks a question, keep it as a question
6. If the user makes a request, phrase it as a direct instruction

Conversation context:
{intent_history}

Raw input: {raw_input}

Output ONLY the refined prompt. No preamble, no explanation.
```

**`distill_system.md`**
```
You are a progress update generator. Given the agent's streaming response so
far and the user's original request, produce a single natural-sounding update.

Rules:
1. ONE sentence. Conversational. Like a colleague updating you.
2. If the agent is still figuring things out: "Looking into it..." / "Checking..."
3. If the agent found something: "Found it — [key finding]"
4. If the agent is going off-topic: null (signal drift to steering engine)
5. If nothing useful yet: null (don't spam)

User intent: {user_intent}
Agent output so far: {partial_output}

Output ONLY the update sentence, or null if nothing to report.
```

**`steer_system.md`**
```
You are a drift detector. Given what the user asked for and what the agent is
currently saying, determine if the agent is going off-topic.

User wanted: {user_intent}
Agent is currently talking about: {current_topic}

Rules:
1. If aligned: output null (no intervention needed)
2. If slightly off but still productive: output null (let it continue)
3. If clearly off-topic: output a brief correction message to inject
4. Correction should be 1 sentence, redirecting to user's original intent

Output: null (aligned) | "Stay focused on [user_intent]. [Redirect suggestion]"
```

### 3. Platform Surfaces

#### Discord Surface (`surfaces/discord_surface.py`)

```python
class DiscordSurface:
    """Renders intermediary output to Discord text channels."""
    
    async def send_refined(self, channel, raw, refined):
        """Send the refined prompt as a quote-reply to the original."""
        await channel.send(f"> {refined}")
    
    async def start_progress(self, channel, initial_text="Working on it..."):
        """Create a message that will be edited with progress."""
        self.progress_msg = await channel.send(initial_text)
    
    async def update_progress(self, text):
        """Edit the progress message (rate-limited to edit_interval_ms)"""
        await self.progress_msg.edit(content=text)
    
    async def send_final(self, channel, summary):
        """Replace progress message with final summary."""
        await self.progress_msg.edit(content=summary)
    
    async def send_steering_notice(self, channel, notice):
        """Show that we redirected the agent."""
        await channel.send(f"🔄 {notice}")
```

Key integration: `DiscordAdapter._voice_text_channels` maps guild_id → text_channel. The surface pulls this from the adapter's existing state.

#### WebUI Surface (`surfaces/webui_surface.py`)

```python
class WebUISurface:
    """Bridges intermediary events to WebUI via Server-Sent Events."""
    
    async def stream_event(self, event_type, data):
        """Push event to WebUI SSE connection."""
        # Event types: refined, progress, steering, final
        self.sse_queue.put({"type": event_type, **data})
```

The WebUI extension consumes these events and renders them in the intermediary pane/sidebar.

#### CLI Surface (`surfaces/cli_surface.py`)

```python
class CLISurface:
    """Renders intermediary status in the CLI/TUI."""
    
    def update_status(self, text):
        """Update status line in TUI."""
        self.cli_ref.update_status_bar(text)
    
    def show_refined(self, raw, refined):
        """Show both raw and refined in transcript."""
        self.cli_ref.print_refined(raw, refined)
```

### 4. Hook Registration (`hooks.py`)

```python
def register_hooks(ctx: PluginContext, intermediary: Intermediary):
    """Register all Hermes plugin hooks."""
    
    @ctx.hook("pre_gateway_dispatch")
    async def on_incoming(event, gateway, session_store):
        """Refine incoming message before agent dispatch."""
        if not event.text:
            return
        
        state = intermediary.get_state(event.session_id)
        refined = await intermediary.refine(event.text, state)
        
        # Store original for surface rendering
        state.last_raw = event.text
        state.last_refined = refined
        
        # Update surface
        await intermediary.surface.send_refined(channel, event.text, refined)
        
        # Replace event text with refined
        event.text = refined
    
    @ctx.hook("pre_llm_call")
    async def on_before_llm(messages, **kwargs):
        """Inject steering message if drift detected."""
        # This adds a correction into the message list if steering is active
        if state := intermediary.active_state:
            if state.pending_steering:
                messages.append({
                    "role": "user",
                    "content": state.pending_steering
                })
                state.pending_steering = None
    
    @ctx.hook("post_llm_call")  
    async def on_after_llm(response, **kwargs):
        """Distill the response and update surface."""
        state = intermediary.active_state
        if state:
            summary = await intermediary.distill(response, state)
            await intermediary.surface.update_progress(summary)
    
    @ctx.hook("on_session_start")
    async def on_session_start(session_id, **kwargs):
        """Initialize intermediary state for new session."""
        intermediary.create_state(session_id)
    
    @ctx.hook("on_session_end")
    async def on_session_end(session_id, **kwargs):
        """Clean up intermediary state."""
        intermediary.destroy_state(session_id)
```

## Integration Points

### Hermes Agent (hermes-agent repo)

| File | What We Touch | How |
|------|---------------|-----|
| `hermes_cli/plugins.py` | Extend `VALID_HOOKS` | Add `intermediary_progress` hook for surfaces |
| `hermes_cli/voice.py` | Bridge voice input | STT → intermediary → send refined to agent |
| `gateway/platforms/discord.py` | Register surface adapter | Inject `DiscordSurface` into `DiscordAdapter` |
| `tools/voice_mode.py` | Pre-process transcript | Run through intermediary before dispatch |
| `hermes_cli/config.py` | Add `intermediary:` config section | Schema + defaults |

### Hermes WebUI (hermes-webui repo)

| File | What We Touch | How |
|------|---------------|-----|
| `static/boot.js` | Add intermediary pipeline | Between STT result and form submit |
| `static/ui.js` | Two-pane composer + sidebar | New DOM elements for intermediary pane |
| `static/panels.js` | Add intermediary preferences | Settings panel with toggles |
| `static/extension_settings.js` | Extension contract | How intermediary registers with WebUI |
| `api/extensions.py` | Expose intermediary endpoints | `/api/intermediary/stream` SSE endpoint |
| `api/upload.py` | Post-process transcribe | Run refined transcript back through |

### External Repos

| Repo | Relevance | Link |
|-------|-----------|------|
| **hermes-agent** | Primary plugin host | `github.com/NousResearch/hermes-agent` |
| **hermes-webui** | Extension host | `github.com/ChonSong/hermes-webui` |
| **discord.py** | Discord voice IO | `github.com/Rapptz/discord.py` |

## Data Flow: Voice Input Example (Discord)

```
1. User speaks in Discord voice channel
2. VoiceReceiver captures PCM (existing)
3. VoiceReceiver.pcm_to_wav() → WAV file (existing)
4. tools.transcription_tools.transcribe_audio() → raw text (existing)
5. ┌── NEW: Intermediary hook ──────────────────┐
6. │ Refine engine: "um the docker thing?"       │
7. │ → "Debug the Docker socket permission error" │
8. │ Store: state.user_intent = refined prompt    │
9. │ Surface: "Looking into the Docker issue..."  │
10. └─────────────────────────────────────────────┘
11. Send refined text to agent (existing dispatch)
12. Agent starts streaming response (existing)
13. ┌── NEW: Distillation ──────────────────────┐
14. │ Buffer tokens, detect milestones           │
15. │ Surface: "Found 3 possible causes..."      │
16. │ Surface: "Narrowing down to socket perms"  │
17. └─────────────────────────────────────────────┘
18. ┌── NEW: Steering ─────────────────────────┐
19. │ Detect agent explaining Docker history     │
20. │ Inject: "Stay focused on the fix"          │
21. └─────────────────────────────────────────────┘
22. Agent delivers final answer (existing)
23. ┌── NEW: Final ─────────────────────────────┐
24. │ Surface: "Fixed. Run: sudo usermod..."    │
25. └─────────────────────────────────────────────┘
```

## Data Flow: Text Example (WebUI)

```
1. User types in WebUI composer
2. (Optional) User speaks → Web Speech API → raw transcript
3. ┌── NEW: Intermediary intercept ────────────┐
4. │ STT result / typed text → refine engine    │
5. │ Two-pane update: raw → refined             │
6. │ User can edit refined before send           │
7. └─────────────────────────────────────────────┘
8. User hits Enter (or auto-send after silence)
9. Refined text sent to agent (existing HTTP)
10. Agent streams back (existing)
11. ┌── NEW: Distillation ──────────────────────┐
12. │ WebUI sidebar shows intermediary updates   │
13. │ "Looking into it..."                       │
14. │ "Found the answer — here it is:"           │
15. └─────────────────────────────────────────────┘
16. Final answer rendered in chat (existing)
```

## Performance Requirements

| Metric | Target | Rationale |
|--------|--------|-----------|
| Refine latency | < 500ms | Feels instant to user |
| Distill update interval | 1-2 seconds | Natural human update cadence |
| Steering decision latency | < 1 second | Catch drift before it goes too far |
| Discord edit interval | 500ms | Rate limit friendly; smooth feel |
| Memory overhead | < 50MB | LLM model is the main cost |
| CPU overhead | < 5% | Prompt caching, small models |

## Security & Privacy

- Refinement LLM calls go through the same provider pipeline as Hermes (shared API keys, shared rate limits)
- No new external dependencies (no new API services)
- Conversation state (intent_history) stays in-memory per session, never persisted
- Plugin respects existing hermes-agent `plugins.enabled` opt-in gate

## Testing Strategy

1. **Unit tests**: Each engine (refine/distill/steer) tested with mocked LLM responses
2. **Integration tests**: Full pipeline test against hermes-agent in mock mode
3. **Surface tests**: Mock Discord channel/WebUI SSE/WebUI DOM to verify rendering
4. **Manual E2E**: Run with real Discord bot + WebUI + voice input

## Success Criteria

- [ ] Raw transcript → refined prompt works correctly for 90% of test cases
- [ ] Distillation produces non-spammy updates (avg < 3 per exchange)
- [ ] Steering reduces off-topic responses by ≥50% (measurable via rating)
- [ ] End-to-end latency added by intermediary < 1 second (excluding agent time)
- [ ] Works on all three platforms (Discord, WebUI, CLI) with consistent behavior
