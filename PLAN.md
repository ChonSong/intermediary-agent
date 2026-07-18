# Intermediary Agent — Complete Plan

## DeepThink Analysis

### Loop 1 — Surface
**Problem**: Design a semantic supervisor that sits between human and AI agent.

**Initial hypothesis**: Build a plugin with 3 engines (refine/distill/steer), hook into existing hermes-agent pipeline, add WebUI extension. Reuse `agent.steer()` for corrections. Audio as pluggable sublayer using TEN/Pipecat/LiveKit.

### Loop 2 — Explore
**Existing skills/knowledge discovered**:
- `agent-pipeline-intermediary` skill — exact same problem, with reference implementations for hermes-agent integration and WebUI extension
- `Playwright (Automation + MCP + Scraper)` — supports video recording of browser tests (frontend evidence)
- `deep-think` — empirical validation is mandatory for running systems

**Integration patterns from skill**:
- `intermediate_state.py`: Per-session state management
- `hooks.py`: Pre-gateway dispatch, pre-LLM call, post-LLM call hook registration
- `discord_surface.py`: Edit-message pattern for progress updates
- `webui_extension/intermediary.js`: SSE consumer for real-time intermediary events

**Audio frameworks**:
- TEN Turn Detection (open-source, best for turn-taking) — https://github.com/ten-framework/ten-framework
- Pipecat (BSD-2, concurrent STT+LLM+TTS) — https://github.com/pipecat-ai/pipecat
- LiveKit (Apache-2, WebRTC browser voice) — https://github.com/livekit/agents

### Loop 3 — Challenge
**What could be wrong with the current approach?**

1. **Steering via `agent.steer()` may not work as expected**
   - The existing `/steer` is a USER command. Intermediary-side injection may require direct `agent._pending_steer` manipulation.
   - Need to verify: Can a plugin call `agent.steer()` or does it need `ctx.inject_message()`?
   - Actually: `ctx.inject_message()` INTERRUPTS. `agent.steer()` does NOT interrupt. We want non-interrupting.
   - Resolution: Plugin should call `agent.steer()` if accessible, else use `ctx.inject_message()` with `role="user"` and rely on the agent's built-in steer queue.

2. **Audio backends may be overkill for MVP**
   - Phase 1 is text-only. Audio can come later.
   - BUT: architecture must NOT preclude audio. The `AudioBackend` base class + configuration pattern is correct.

3. **Refine/distill/steer each require LLM calls — latency triple?**
   - Mitigation: Each engine is small/fast. Refine = single call (user waits). Distill = concurrent with agent. Steer = concurrent with agent.
   - Total added latency: < 500ms for refine. Distill/steer are concurrent (0 added latency).

4. **Existing hermes-agent `VALID_HOOKS` may not support what we need**
   - Need to check if `intermediary_*` hooks need to be added, or if we reuse `pre_gateway_dispatch` + `pre_llm_call` + `post_llm_call`.
   - The `pre_gateway_dispatch` hook gets `event: MessageEvent` BEFORE agent dispatch — perfect for refine.
   - The `pre_llm_call` hook gets `messages` list — can inject steering.
   - The `post_llm_call` hook gets `response` — can trigger distillation.
   - Verdict: NO new hooks needed for Phase 1. Add `intermediary_*` hooks only for external observability.

### Loop 4 — Synthesize
**Final architecture**:

| Component | Mechanism | Existing/New |
|-----------|-----------|--------------|
| Refine engine | `pre_gateway_dispatch` hook → rewrite `event.text` | Existing hook, new handler |
| Distill engine | `post_llm_call` hook → distill response | Existing hook, new handler |
| Steer engine | `pre_llm_call` hook → inject into messages (via `agent.steer()` if accessible, else `ctx.inject_message()`) | Existing hook, new handler |
| State manager | Per-session `IntermediaryState` | New |
| Discord surface | Edit-message pattern using `DiscordAdapter.edit_message()` | Existing method |
| WebUI surface | SSE endpoint `/api/intermediary/stream` + two-pane composer | New |
| Audio sublayer | `AudioBackend` ABC with TEN/Pipecat/LiveKit implementations | New |

### Loop 5 — Convergence
**Stable**: Yes. Architecture reuses existing hooks, doesn't reinvent steering, pluggable audio, text-first MVP.

---

## Component Design

### 1. Refine Engine (`intermediary/refine.py`)

```python
class RefineEngine:
    """Restructure messy user input into actionable prompts."""
    
    async def refine(self, raw_text: str, state: IntermediaryState, context: dict) -> str:
        """
        Args:
            raw_text: User's raw transcript or typed text
            state: Per-session state (intent_history for pronoun resolution)
            context: Additional context (platform, conversation history)
        
        Returns:
            Refined, actionable prompt
        """
        # 1. Resolve pronouns using intent_history
        # 2. Expand vague references
        # 3. Structure as [Action] + [Context] + [Constraints]
        # 4. Single LLM call with small model
        pass
```

**Prompt** (`prompts/refine_system.md`):
```
You are an input refinement engine. Restructure messy spoken/typed input into
a clear, actionable prompt for an AI agent.

Rules:
1. Preserve the user's original intent exactly
2. Resolve pronouns using conversation context
3. Expand vague references ("that thing", "the error") to specific terms
4. Structure as: [Action] + [Context] + [Constraints]
5. If the user asks a question, keep it as a question
6. If the user makes a request, phrase it as a direct instruction
7. Output ONLY the refined prompt. No preamble, no explanation.

Conversation context: {intent_history}
Raw input: {raw_input}
```

### 2. Distill Engine (`intermediary/distill.py`)

```python
class DistillEngine:
    """Watch agent's streaming output and produce natural progress updates."""
    
    def __init__(self):
        self.buffer = ""
        self.last_update = time.monotonic()
    
    async def on_token(self, token: str, state: IntermediaryState) -> Optional[str]:
        """
        Called for each streaming token from agent.
        
        Returns:
            Progress update text, or null if nothing to report.
        """
        self.buffer += token
        
        # Check if it's time for an update (1-2s cadence)
        if time.monotonic() - self.last_update > 1.5:
            update = await self._maybe_summarize(state)
            if update:
                self.last_update = time.monotonic()
                return update
        return None
    
    async def _maybe_summarize(self, state: IntermediaryState) -> Optional[str]:
        """Produce a milestone update if there's something to report."""
        # 1. Check for topic shift or completion
        # 2. If milestone reached: produce natural 1-sentence update
        # 3. Otherwise: return null (don't spam)
        pass
```

**Prompt** (`prompts/distill_system.md`):
```
You are a progress update generator. Given the agent's streaming output so
far and the user's original request, produce a single natural-sounding update.

Rules:
1. ONE sentence. Conversational. Like a colleague updating you.
2. If the agent is still figuring things out: "Looking into it..." / "Checking..."
3. If the agent found something: "Found it — [key finding]"
4. If the agent is going off-ttopic: output "DRIFT" (signal to steering engine)
5. If nothing useful yet: output null

User intent: {user_intent}
Agent output: {partial_output}

Output ONLY the update sentence, or null if nothing to report.
```

### 3. Steer Engine (`intermediary/steer.py`)

```python
class SteerEngine:
    """Detect agent drift and inject corrections mid-turn."""
    
    async def check_drift(self, partial_output: str, state: IntermediaryState) -> Optional[str]:
        """
        Args:
            partial_output: Agent's output so far this turn
            state: Per-session state with drift_baseline
        
        Returns:
            Correction message to inject, or null if aligned.
        """
        # 1. Compare topic of partial_output vs drift_baseline
        # 2. Compute drift_confidence (0.0 to 1.0)
        # 3. If drift_confidence > threshold: draft correction
        # 4. Else: return null
        pass
    
    async def inject(self, plugin_ctx: PluginContext, session_id: str, correction: str):
        """
        Inject correction into agent's next tool result.
        NON-interrupting (uses agent.steer() mechanism).
        """
        # Option A: If plugin_ctx.steer_agent(session_id, text) exists
        # Option B: If we have cached agent reference: agent.steer(correction)
        # Option C: Fallback to ctx.inject_message() (interrupts)
        pass
```

**Prompt** (`prompts/steer_system.md`):
```
You are a drift detector for an AI agent. Determine if the agent is going
off-topic compared to what the user originally asked for.

User wanted: {user_intent}
Agent is talking about: {current_topic}

Rules:
1. If aligned: output null (no intervention)
2. If slightly off but productive: output null (let it continue)
3. If clearly off-topic: output a 1-sentence correction for the agent
4. Correction should be: "Stay focused on [user_intent]. [Redirect suggestion]"

Output: null | correction text
```

### 4. State Manager (`intermediary/state.py`)

```python
@dataclass
class IntermediaryState:
    session_id: str
    user_intent: str = ""           # Resolved user intent (no pronouns)
    intent_history: list[str] = field(default_factory=list)  # Previous intents for pronoun resolution
    drift_baseline: str = ""        # What we're checking against for drift
    current_topic: str = ""         # What the agent is currently discussing
    steer_injected: bool = False    # Track if we already steered this exchange
    message_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
```

### 5. Hook Registration (`intermediary/hooks.py`)

```python
def register_hooks(ctx: PluginContext, intermediary: Intermediary):
    """Register all Hermes plugin hooks."""
    
    @ctx.register_hook("pre_gateway_dispatch")
    async def on_incoming(event, gateway, session_store):
        """Refine incoming message before agent dispatch."""
        if not event.text:
            return
        
        state = intermediary.get_state(event.session_id)
        refined = await intermediary.refine(event.text, state, {
            "platform": event.platform.value,
        })
        
        # Store original + refined
        state.last_raw = event.text
        state.last_refined = refined
        state.user_intent = refined  # Update baseline
        state.intent_history.append(refined)
        
        # Show refined via surface
        await intermediary.surface.send_refined(event, event.text, refined)
        
        # Replace event text with refined
        event.text = refined
    
    @ctx.register_hook("pre_llm_call")
    async def on_before_llm(messages, session_id, **kwargs):
        """Inject steering message if drift was detected."""
        state = intermediary.get_state(session_id)
        if state and state.pending_steering:
            # Inject via agent.steer() or messages.append()
            messages.append({
                "role": "user",
                "content": f"[User guidance] {state.pending_steering}"
            })
            state.pending_steering = None
    
    @ctx.register_hook("post_llm_call")
    async def on_after_llm(response, session_id, **kwargs):
        """Distill the response and update surface."""
        state = intermediary.get_state(session_id)
        if state:
            summary = await intermediary.distill(response, state)
            await intermediary.surface.update_progress(summary)
```

### 6. Audio Sublayer (`audio/`)

```python
class AudioBackend(ABC):
    """Pluggable audio IO for full-duplex voice."""
    
    @abstractmethod
    async def start_listening(self, user_id: str) -> AsyncIterator[bytes]:
        """Stream raw audio chunks from user microphone."""
    
    @abstractmethod
    async def speak(self, audio: bytes) -> None:
        """Play audio to user."""
    
    @abstractmethod
    async def stop_speaking(self) -> None:
        """Barge-in: immediately stop playback when user starts talking."""
    
    @abstractmethod
    async def detect_turn(self, audio_stream) -> AsyncIterator[TurnEvent]:
        """Yield TurnEvent(is_user_speaking, is_end_of_turn)."""
```

**Concrete backends**: `TENAudioBackend`, `PipecatAudioBackend`, `LiveKitAudioBackend`

### 7. Platform Surfaces

#### Discord Surface (`surfaces/discord_surface.py`)

- `send_refined()`: Show `> refined text` as quote-reply to original message
- `start_progress()`: Create message that will be edited with progress
- `update_progress()`: Edit the progress message (rate-limited to 500ms)
- `send_final()`: Replace progress with final summary

#### WebUI Surface (`surfaces/webui_surface.py`)

- SSE bridge to `/api/intermediary/stream`
- Event types: `refined`, `progress`, `steering`, `final`

---

## Data Flow

### Text Path (Phase 1)
```
User types in Discord/CLI/WebUI
  → pre_gateway_dispatch hook
    → intermediary.refine(raw_text)
    → surface.send_refined(raw, refined)
    → event.text = refined (replace for agent)
  → Agent processes refined prompt
  → Streaming response
    → intermediary.distill() → surface.update_progress()
    → intermediary.steer.detect() → if drift: agent.steer("redirect")
  → Agent completes
    → surface.send_final(summary)
```

### Voice Path (Phase 2+)
```
User speaks in Discord VC
  → VoiceReceiver captures PCM (existing)
  → STT via transcription_tools (existing)
  → raw transcript → intermediary.refine()
  → Agent processes
  → Streaming response → intermediary.distill()
  → Agent completes → TTS → speak in VC
    → Meanwhile: TEN/Pipecat detects barge-in → stop_speaking() → back to listening
```

---

## Test Strategy

### Overview

All tests MUST be empirically validated (per `deep-think` skill). Session transcripts and code-reading over-report bugs by ~5x. We test by running the real system.

### Test Types

| Type | Tool | Evidence | When |
|------|------|----------|------|
| **Unit test** | pytest | Terminal output | Every engine |
| **Integration test** | pytest + mock hermes-agent | Terminal output | Phase 1.3+ |
| **Frontend test** | Playwright (headless browser) | Screenshot + video | Phase 4+ |
| **Voice test** | Playwright + mic simulation | Video + audio recording | Phase 2+ |
| **Manual E2E** | Human in Discord/WebUI | Video recording (screen capture) | Every phase |

### Video Evidence (per user's request)

For frontend and voice tests, we record video evidence using Playwright's built-in video recording:

```python
# In Playwright test config:
browser = await playwright.chromium.launch(
    record_video_dir="test-evidence/videos/",
    record_video_size={"width": 1280, "height": 720}
)
```

**Video evidence is stored in**: `test-evidence/videos/{test-name}-{timestamp}.webm`

**When to record**:
- Phase 2+: Voice input tests (show mic → STT → refine → agent response)
- Phase 4+: WebUI two-pane composer tests (show raw → refined → send → progress)
- Phase 4+: Discord edit-message pattern tests (show progress being edited in place)

### Phase 1 Test Plan (Text-Only)

| Test | Type | Evidence |
|------|------|----------|
| Refine engine produces structured prompt | Unit | Terminal |
| Refine resolves pronouns using history | Unit | Terminal |
| Distill produces ≤3 updates per exchange | Unit | Terminal |
| Steer detects drift and injects correction | Unit | Terminal |
| Hook registration works with mock hermes-agent | Integration | Terminal |
| Discord surface edits message (not new) | Integration | Terminal |
| End-to-end: raw → refined → progress → final | Manual E2E | Screen recording |

### Phase 2 Test Plan (Voice)

| Test | Type | Evidence |
|------|------|----------|
| VoiceReceiver → STT → refine pipeline | Integration | Terminal |
| Interim refinement while speaking | Manual E2E | Video |
| Barge-in: user speaks → agent stops | Manual E2E | Video |
| Turn detection: agent knows when to yield | Manual E2E | Video |

### Phase 4 Test Plan (WebUI)

| Test | Type | Evidence |
|------|------|----------|
| Two-pane composer renders | Playwright | Screenshot |
| Real-time refinement as user types | Playwright | Video |
| Sidebar shows progress updates | Playwright | Video |
| Settings persist across reload | Playwright | Screenshot |
| Voice button triggers intermediary | Playwright | Video |

---

## Integration Points

### hermes-agent Changes (minimal)

| File | Change |
|------|--------|
| `hermes_cli/plugins.py` | Add `intermediary_*` hooks to `VALID_HOOKS` (for observability) |
| `hermes_cli/plugins.py` | Add `ctx.steer_agent(session_id, text)` method |
| `hermes_cli/config.py` | Add `intermediary:` config section |
| `gateway/platforms/discord.py` | Wire intermediary surface (minimal) |

### hermes-webui Changes

| File | Change |
|------|--------|
| `static/extension_settings.js` | Register intermediary extension |
| `static/boot.js` | Intercept STT/text input, refine |
| `static/ui.js` | Two-pane composer + sidebar |
| `static/panels.js` | Intermediary preferences |
| `api/extensions.py` | SSE endpoint |
| `api/upload.py` | Refine after STT |

---

## External Dependencies

| Dependency | Repo | License | Use Case |
|---|---|---|---|
| **hermes-agent** | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | — | Plugin host, agent.steer(), hooks |
| **hermes-webui** | [ChonSong/hermes-webui](https://github.com/ChonSong/hermes-webui) | — | Extension host, browser UI |
| **discord.py** | [Rapptz/discord.py](https://github.com/Rapptz/discord.py) | MIT | Voice IO, edit_message |
| **TEN Framework** | [TEN-framework](https://github.com/ten-framework/ten-framework) | Open-source | Full-duplex turn detection |
| **TEN Turn Detection** | [HuggingFace](https://huggingface.co/TEN-framework/TEN_Turn_Detection) | Open-source | Yield-floor detection |
| **TEN VAD** | [HuggingFace](https://huggingface.co/TEN-framework/ten-vad) | Open-source | Voice activity detection |
| **Pipecat** | [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | BSD-2 | Concurrent STT+LLM+TTS |
| **LiveKit** | [livekit/agents](https://github.com/livekit/agents) | Apache-2 | WebRTC browser voice |
| **Langfuse** | [langfuse/langfuse](https://github.com/langfuse/langfuse) | MIT | Observability (optional) |

---

## Performance Requirements

| Metric | Target | Rationale |
|--------|--------|-----------|
| Refine latency | < 500ms | Feels instant |
| Distill update interval | 1-2 seconds | Natural cadence |
| Steer decision | < 1 second | Catch drift early |
| Discord edit interval | 500ms | Rate-limit friendly |
| Barge-in response | < 200ms | User speaks → agent stops |
| Turn detection | < 100ms | TEN model runs locally |
| Memory overhead | < 100MB | TEN model + audio buffers |
| CPU overhead | < 10% | Exclude LLM/agent cost |

---

## Security & Privacy

- Steer injection uses existing `agent.steer()` — same auth model
- Audio sublayer streams locally (no cloud audio processing unless configured)
- TEN model runs locally (no API calls for turn detection)
- Conversation state (intent_history) stays in-memory per session, never persisted
- Plugin respects existing `plugins.enabled` opt-in gate
- No PII in logs at INFO level (only DEBUG + redacted)

---

## Repo Structure

```
intermediary-agent/
  README.md
  PLAN.md                    # This file
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
  test-evidence/
    videos/                  # Playwright video recordings
    screenshots/             # Playwright screenshots
```
