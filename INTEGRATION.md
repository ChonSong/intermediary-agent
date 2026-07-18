# Integration Points

> Detailed file paths, function signatures, and links for integrating the intermediary agent with hermes-agent and hermes-webui.

---

## External Repositories

| Repo | URL | Description |
|------|-----|-------------|
| **hermes-agent** | https://github.com/NousResearch/hermes-agent | Core agent, plugin system, gateway, voice IO |
| **hermes-webui** | https://github.com/ChonSong/hermes-webui | Browser-based chat UI, extensions, settings |
| **discord.py** | https://github.com/Rapptz/discord.py | Discord bot library (voice, messaging) |
| **Langfuse** | https://github.com/langfuse/langfuse | Observability (optional, already integrated) |

---

## hermes-Agent Integration

### 1. Plugin System (`hermes_cli/plugins.py`)

**Add to `VALID_HOOKS`** (line ~75):

```python
VALID_HOOKS: Set[str] = {
    "pre_tool_call",
    "post_tool_call",
    "transform_terminal_output",
    "transform_tool_result",
    "pre_llm_call",
    "post_llm_call",
    "pre_api_request",
    "post_api_request",
    "on_session_start",
    "on_session_end",
    "on_session_finalize",
    "on_session_reset",
    "subagent_stop",
    "pre_gateway_dispatch",
    "pre_approval_request",
    "post_approval_response",
    # NEW: intermediary lifecycle
    "intermediary_refined",      # after intermediary refines input
    "intermediary_distilled",    # after intermediary distills output  
    "intermediary_steered",      # after intermediary injects steering
}
```

**`PluginContext` API** (line ~230):

```python
class PluginContext:
    def register_tool(...) -> None: ...
    def inject_message(content: str, role: str = "user") -> bool: ...
    def register_cli_command(...) -> None: ...
    def register_command(...) -> None: ...
    def dispatch_tool(tool_name: str, args: dict, **kwargs) -> str: ...
    def register_context_engine(engine) -> None: ...
    
    # NEW: intermediary hooks
    def on_intermediary_event(event: str, data: dict) -> None: ...
```

### 2. Discord Adapter (`gateway/platforms/discord.py`)

**`DiscordAdapter.__init__`** — Add intermediary state (line ~494):

```python
class DiscordAdapter(BasePlatformAdapter):
    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.DISCORD)
        # ...existing code...
        
        # NEW: intermediary surface
        self._intermediary = None  # set by run.py after plugin load
        self._intermediary_progress_msg = None  # guild_id -> Message
```

**`edit_message()`** — Already exists (line ~1288), reuse directly:

```python
async def edit_message(self, message_id: str, new_content: str) -> bool:
    """Edit an existing Discord message. Used by intermediary for progress updates."""
    # existing implementation works
```

**`VoiceReceiver`** — Already exists (line ~121). No modification needed. The intermediary hooks into the existing voice input callback:

```python
# In run.py or gateway runner:
adapter._voice_input_callback = intermediary.handle_voice_input
```

**`_voice_input_callback`** (line ~514):

```python
self._voice_input_callback: Optional[Callable] = None
# Called by VoiceReceiver.check_silence() polling loop with:
#   (guild_id, user_id, wav_path)
```

### 3. Voice Input (`tools/voice_mode.py`)

**STT Pipeline** — Existing flow:

```
User speaks → VoiceReceiver → pcm_to_wav() → transcribe_audio() → text
```

**Intermediary intercept** — Wrap `transcribe_audio`:

```python
# In intermediary/hooks.py
async def handle_voice_input(guild_id: str, user_id: str, wav_path: str):
    # 1. Transcribe (existing)
    raw = transcribe_audio(wav_path)
    
    # 2. Refine (new)
    refined = await intermediary.refine(raw, state)
    
    # 3. Send to agent (existing dispatch)
    await dispatch_to_agent(guild_id, user_id, refined)
```

### 4. Config (`hermes_cli/config.py`)

**Add `intermediary:` config section** (alongside `voice:`, `stt:`, `tts:`):

```python
# In config.py schema:
INTERMEDIARY_DEFAULTS = {
    "enabled": False,
    "features": {
        "refine": True,
        "distill": True,
        "steer": True,
    },
    "models": {
        "refine": "default",
        "distill": "default", 
        "steer": "default",
    },
    "thresholds": {
        "drift_confidence": 0.7,
        "silence_ms": 1800,
    },
    "platforms": {
        "discord": {
            "edit_interval_ms": 500,
            "max_update_length": 1800,
        },
        "webui": {
            "stream_mode": "sentence",
        },
        "cli": {
            "spinner": True,
        },
    },
}
```

### 5. Gateway Runner (`gateway/run.py` or equivalent)

**Wire intermediary to adapters:**

```python
# In gateway startup:
for adapter in platform_adapters:
    if hasattr(adapter, '_intermediary'):
        adapter._intermediary = intermediary_instance
```

---

## hermes-WebUI Integration

### 1. Extension System (`static/extension_settings.js`)

**Register intermediary extension:**

```javascript
// In extension_settings.js:
const INTERMEDIARY_EXTENSION = {
    id: 'intermediary',
    name: 'Intermediary',
    description: 'Semantic supervisor for input refinement and output distillation',
    version: '0.1.0',
    author: 'codeovertcp',
    css: ['/extensions/intermediary/intermediary.css'],
    js: ['/extensions/intermediary/intermediary.js'],
    settings: [
        { key: 'refine_enabled', type: 'boolean', default: true },
        { key: 'distill_enabled', type: 'boolean', default: true },
        { key: 'steer_enabled', type: 'boolean', default: true },
        { key: 'auto_send', type: 'boolean', default: false },
        { key: 'stream_mode', type: 'enum', options: ['token', 'sentence', 'manual'], default: 'sentence' },
    ],
    hooks: [
        'hermes:pipeline:preSend',
        'hermes:voice:transcribed',
        'hermes:agent:token',
        'hermes:agent:complete',
    ]
};

// Register with extension manager
extensionManager.register(INTERMEDIARY_EXTENSION);
```

### 2. Voice Pipeline (`static/boot.js`)

**Intercept STT result** (around line 723):

```javascript
// Existing voice input flow (simplified):
// _onSpeechResult → form.submit()

// NEW: intermediary intercept
async function _onSpeechResult(event) {
    const raw = _extractTranscript(event);
    
    // Let intermediary refine
    const refined = await window._intermediaryRefine(raw);
    
    // Update composer with both panes
    _updateComposerPanes(raw, refined);
    
    // If auto-send is enabled, submit after silence
    if (intermediarySettings.auto_send) {
        _scheduleAutoSend(refined);
    }
}
```

### 3. Composer UI (`static/index.html`)

**Two-pane composer markup:**

```html
<!-- Add inside #composer-area -->
<div id="intermediary-pane" class="intermediary-pane hidden">
    <div class="intermediary-header">
        <span class="intermediary-status">Ready</span>
        <button id="intermediary-toggle" class="intermediary-toggle">⚙</button>
    </div>
    <div id="intermediary-raw" class="intermediary-raw" readonly></div>
    <div id="intermediary-refined" class="intermediary-refined" contenteditable="true"></div>
</div>

<!-- Sidebar for progress -->
<aside id="intermediary-sidebar" class="intermediary-sidebar hidden">
    <h3>Intermediary</h3>
    <div id="intermediary-updates" class="intermediary-updates"></div>
</aside>
```

### 4. Settings Panel (`static/panels.js`)

**Add intermediary preferences:**

```javascript
// In panels.js settings render:
const intermediaryHtml = `
    <div class="setting-group">
        <label>Refine input
            <input type="checkbox" id="intermediaryRefineEnabled" data-key="refine_enabled">
        </label>
        <label>Distill output
            <input type="checkbox" id="intermediaryDistillEnabled" data-key="distill_enabled">
        </label>
        <label>Steer agent
            <input type="checkbox" id="intermediarySteerEnabled" data-key="steer_enabled">
        </label>
        <label>Auto-send after silence
            <input type="checkbox" id="intermediaryAutoSend" data-key="auto_send">
        </label>
    </div>
`;
```

### 5. Backend API (`api/extensions.py`)

**SSE endpoint for intermediary events:**

```python
# In api/extensions.py:
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

intermediary_router = APIRouter()

@intermediary_router.get("/api/intermediary/stream")
async def intermediary_stream(request: Request):
    """SSE stream for intermediary events."""
    async def event_generator():
        queue = asyncio.Queue()
        # Register queue with intermediary
        intermediary.register_webui_queue(queue)
        try:
            while True:
                if await request.is_disconnected():
                    break
                event = await asyncio.wait_for(queue.get(), timeout=30)
                yield {"event": event["type"], "data": json.dumps(event["data"])}
        except asyncio.TimeoutError:
            yield {"event": "ping", "data": "{}"}
    return EventSourceResponse(event_generator())
```

### 6. Transcription API (`api/upload.py`)

**Refine after STT** (line ~435):

```python
# In handle_transcribe:
def handle_transcribe(handler):
    # ...existing: receive file, save to temp...
    
    # Existing: transcribe
    result = transcribe_audio(temp_path)
    raw_transcript = result["transcript"]
    
    # NEW: refine if intermediary is enabled
    if intermediary_enabled():
        refined = intermediary.refine(raw_transcript)
        result["refined"] = refined
    
    # Return both raw and refined
    send_response(200, result)
```

---

## Data Flow Summary

```
DISCORD VOICE:
  VoiceReceiver._on_packet()
    → VoiceReceiver.check_silence()
      → _voice_input_callback()
        → intermediary.handle_voice_input()
          → transcribe_audio()  [STT]
          → intermediary.refine()
          → DiscordSurface.send_refined()
          → dispatch_to_agent()  [existing]
            → Agent streams response
              → intermediary.distill()
                → DiscordSurface.update_progress()
              → intermediary.steer() [if drift]
                → ctx.inject_message()
              → Agent completes
                → DiscordSurface.send_final()

DISCORD TEXT:
  DiscordAdapter.on_message()
    → _voice_input_callback()  [or _text_input_callback]
      → intermediary.refine()
      → DiscordSurface.send_refined()
      → dispatch_to_agent()
        → [same distillation/steering as above]

WEBUI TEXT:
  _onSpeechResult() / form.submit()
    → intermediary.refine()  [via JS API]
    → _updateComposerPanes()
    → [user edits if needed]
    → form.submit()
      → POST /api/chat  [existing]
        → Agent streams response
          → intermediary.distill()  [via SSE]
            → intermediary.sidebar.update()

CLI:
  _read_input()
    → intermediary.refine()
    → CLISurface.show_refined()
    → agent.chat()
      → [same distillation/steering as above]
```

---

## Files Created / Modified

### New Files (in this repo)

```
intermediary-agent/
  README.md
  PLAN.md
  ROADMAP.md
  INTEGRATION.md              # This file
  intermediary/
    __init__.py               # register() entry
    plugin.yaml               # Plugin manifest
    config.py                 # Config schema
    state.py                  # IntermediaryState
    refine.py                 # Refine engine
    distill.py                # Distill engine  
    steer.py                  # Steer engine
    hooks.py                  # Hook registration
  surfaces/
    __init__.py
    discord_surface.py        # Discord renderer
    webui_surface.py          # WebUI SSE bridge
    cli_surface.py            # CLI status line
  prompts/
    refine_system.md          # Refinement prompt
    distill_system.md         # Distillation prompt
    steer_system.md           # Steering prompt
  webui_extension/
    intermediary.css          # Styles
    intermediary.js           # Client logic
    manifest.json             # Extension manifest
  tests/
    test_state.py
    test_refine.py
    test_distill.py
    test_steer.py
    test_hooks_integration.py
    test_discord_surface.py
    test_webui_surface.py
    test_cli_surface.py
```

### Modified Files (in hermes-agent/hermes-webui)

```
hermes-agent/
  hermes_cli/plugins.py           # Add intermediary hooks to VALID_HOOKS
  gateway/platforms/discord.py    # Wire intermediary surface (minimal)
  hermes_cli/config.py            # Add intermediary: config section
  gateway/run.py                  # Connect intermediary to adapters
    
hermes-webui/
  static/extension_settings.js    # Register intermediary extension
  static/boot.js                  # Intercept voice input, refine
  static/ui.js                    # Two-pane composer rendering
  static/panels.js                # Intermediary preferences
  static/index.html               # Composer markup + sidebar
  api/extensions.py               # SSE endpoint
  api/upload.py                   # Refine after STT
```

---

## Quick Reference: Hermes-Agent Plugin API

### Hooks (lifecycle callbacks)

```python
def register_hook(self, name: str, callback: Callable) -> None:
    """Register a callback for a specific hook."""

# Example:
ctx.register_hook("pre_gateway_dispatch", my_callback)
ctx.register_hook("on_session_start", my_session_start)
```

### Context Injection

```python
ctx.inject_message("Stay focused on the fix", role="user")
# → Injects a message into the active conversation
# → If agent is mid-turn, interrupts and injects
# → If agent is idle, queues as next input
```

### Tool Registration

```python
ctx.register_tool(
    name="my_tool",
    toolset="my_plugin",
    schema={"type": "object", "properties": {...}},
    handler=my_handler,
)
```

### Slash Commands

```python
ctx.register_command(
    name="mymodal",
    handler=my_command_handler,
    description="Short description",
    args_hint="<file>",
)
```
