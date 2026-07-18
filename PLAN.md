# Intermediary Agent — Complete Plan

## Vision

A semantic supervisor that sits between the human and Hermes. It **refines** messy input, **distills** verbose output into natural progress updates, and **steers** the agent back on track by hooking into the existing `agent.steer()` mechanism. Includes a pluggable full-duplex audio layer for future voice use.

## Problem Statement

| Friction | Example | Cost |
|----------|---------|------|
| Input friction | "um the docker thing?" requires 3 clarifications | Time, frustration |
| Output friction | Agent gives 5-paragraph essay when user wants the command | User gives up reading |
| Drift friction | Agent explains Docker history instead of fixing the bug | User must interrupt and restart |
| Voice friction | Existing voice mode is half-duplex (can't hear while speaking) | Robotic conversation |

Existing frameworks (Pipecat/LiveKit/TEN) solve *audio transport* but not *semantic supervision*. This repo solves both: an intermediary for meaning, with a plug-in layer for full-duplex audio when needed.

---

## Architecture

### Layered Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         HERMES AGENT                                   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    INTERMEDIARY PLUGIN                           │   │
│  │                                                                  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │   │
│  │  │   Refine     │  │   Distill    │  │   Steer              │ │   │
│  │  │   Engine     │  │   Engine     │  │   Engine             │ │   │
│  │  │              │  │              │  │                      │ │   │
│  │  │ STT → refine │  │ buffer →     │  │ detect drift →      │ │   │
│  │  │ → structured │  │ summarize →  │  │ call agent.steer()  │ │   │
│  │  │   prompt     │  │ progress msg │  │ (NON-interrupting)   │ │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘ │   │
│  │          │                  │                    │              │   │
│  │  ┌───────┴──────────────────┴────────────────────┴───────────┐ │   │
│  │  │                   State Manager                           │ │   │
│  │  │  • intent_history (pronoun resolution)                    │ │   │
│  │  │  • drift_baseline (what user asked for)                   │ │   │
│  │  │  • steer_queue (pending corrections)                      │ │   │
│  │  └──────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              AUDIO SUBLAYER (pluggable)                          │   │
│  │                                                                  │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐ │   │
│  │  │   TEN Turn     │  │   Pipecat      │  │   LiveKit        │ │   │
│  │  │   Detection    │  │   Pipeline     │  │   Transport      │ │   │
│  │  │                │  │                │  │                  │ │   │
│  │  │ Yield-floor    │  │ STT+LLM+TTS    │  │ WebRTC for       │ │   │
│  │  │ detection      │  │ concurrent     │  │ browser voice    │ │   │
│  │  │ (open-source)  │  │ (open-source)  │  │ (heavy)          │ │   │
│  │  └────────────────┘  └────────────────┘  └──────────────────┘ │   │
│  │                                                                  │   │
│  │  Barge-in: user speaks → agent's TTS stops → back to listening │   │
│  │  Turn-taking: agent knows when to yield the floor               │   │
│  │  Echo cancelation: agent doesn't hear its own output            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Hermes Core (existing)                        │   │
│  │  • agent.steer() — inject into next tool result (no interrupt)  │   │
│  │  • inject_message() — interrupt and inject                       │   │
│  │  • VoiceReceiver — Discord voice capture                         │   │
│  │  • transcription_tools — STT providers                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Difference from Earlier Plan

**Before**: Steering used `inject_message()` (interrupts agent). Audio was an afterthought.

**Now**: Steering hooks into `agent.steer()` (injects into next tool result without interrupting). Audio is a pluggable sublayer from day one.

---

## Hermes-Agent Hook Integration

### Using Existing `/steer` Mechanism

The intermediary must NOT reinvent steering. Existing mechanism:

```python
# In AIAgent (agent/aiagent.py or similar)
class AIAgent:
    def steer(self, text: str) -> bool:
        """Store steer text. Next tool result will include 'User guidance: <text>'."""
        with self._pending_steer_lock:
            if self._pending_steer is None:
                self._pending_steer = text
            else:
                self._pending_steer += f"\n{text}"
        return True
    
    def _drain_pending_steer(self):
        """Called by agent loop after tool results are collected."""
        with self._pending_steer_lock:
            text = self._pending_steer
            self._pending_steer = None
            return text
```

The intermediary's steer engine calls `agent.steer("Stay focused on fixing the bug")`. The agent's next tool result gets `User guidance: Stay focused on fixing the bug` appended. No interruption.

### Plugin Hooks Needed

```python
# In hermes_cli/plugins.py VALID_HOOKS, add:
VALID_HOOKS: Set[str] = {
    # ... existing hooks ...
    
    # Intermediary lifecycle
    "intermediary_refined",      # after intermediary refines input
    "intermediary_distilled",    # after intermediary distills output
    "intermediary_steered",      # after intermediary injects steering
}
```

### PluginContext Additions

```python
# In hermes_cli/plugins.py PluginContext:
class PluginContext:
    # ... existing methods ...
    
    def get_cached_agent(self, session_id: str) -> Optional[AIAgent]:
        """Get cached AIAgent for steer injection (gateway mode)."""
        # Access SESSION_AGENT_CACHE from api.config (webui) or equivalent
        ...
    
    def steer_agent(self, session_id: str, text: str) -> bool:
        """Call agent.steer() without interrupting the agent."""
        agent = self.get_cached_agent(session_id)
        if agent and hasattr(agent, 'steer'):
            return agent.steer(text)
        return False
```

---

## Component Design

### 1. Refine Engine (`intermediary/refine.py`)

- Input: raw transcript + conversation context (intent_history)
- Output: structured, actionable prompt
- Quick: small model, single LLM call (<500ms target)
- Handles pronoun resolution ("that thing", "what we discussed")

### 2. Distill Engine (`intermediary/distill.py`)

- Input: streaming tokens from agent (via hook)
- Output: natural progress updates (1 sentence)
- Buffer tokens, detect milestones (topic shifts, completions)
- Non-blocking: runs concurrently with agent output

### 3. Steer Engine (`intermediary/steer.py`)

- **Hooks into existing `agent.steer()` — does NOT reinvent it**
- Input: streaming tokens + user_intent baseline
- Detect drift by comparing topic of output vs user_intent
- If drift_confidence > threshold: `agent.steer("Stay focused on ...")`
- Rate-limited: max 1 steer injection per exchange

### 4. State Manager (`intermediary/state.py`)

```python
@dataclass
class IntermediaryState:
    session_id: str
    intent_history: list[str]      # Previous intents (for pronoun resolution)
    drift_baseline: str           # What the agent should be doing
    current_topic: str            # What the agent is currently discussing
    steer_injected: bool          # Track if we already steered this exchange
    message_queue: asyncio.Queue  # Pending intermediary messages
```

### 5. Audio Sublayer (`audio/`)

Pluggable audio backends. Abstract base class:

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
        """Yield TurnEvent(is_user_speaking, is_end_of_turn) for turn-taking."""
```

**Concrete implementations:**

| Backend | Transport | Use Case | License |
|---------|-----------|----------|---------|
| `TENAudioBackend` | Custom | Full-duplex with TEN Turn Detection | Open-source |
| `PipecatAudioBackend` | WebSocket | STT+LLM+TTS concurrent pipeline | BSD-2 |
| `LiveKitAudioBackend` | WebRTC | Browser-based voice | Apache-2 |
| `DiscordAudioBackend` | Discord VC | Existing hermes-agent Discord voice | (existing) |

**TEN Turn Detection integration:**

```python
# audio/ten_backend.py
class TENAudioBackend(AudioBackend):
    """Full-duplex audio using TEN Framework for turn detection."""
    
    def __init__(self):
        # Load TEN Turn Detection model from HuggingFace
        self.turn_detector = TEN_Turn_Detection.from_pretrained(
            "TEN-framework/TEN_Turn_Detection"
        )
    
    async def detect_turn(self, audio_stream):
        """Use TEN's model to detect when user is done speaking."""
        async for chunk in audio_stream:
            result = self.turn_detector.predict(chunk)
            yield TurnEvent(
                is_user_speaking=result.is_speaking,
                is_end_of_turn=result.is_end_of_turn,
                should_yield_floor=result.should_yield
            )
```

### 6. Platform Surfaces

#### Discord Surface (`surfaces/discord_surface.py`)

- Two modes: **text channel** (progress updates) and **voice channel** (audio sublayer)
- Text: edit-message pattern (existing `DiscordAdapter.edit_message()`)
- Voice: bridge `VoiceReceiver` → STT → intermediary → agent, then TTS back to VC

#### WebUI Surface (`surfaces/webui_surface.py`)

- Two-pane composer (raw + refined)
- Intermediary sidebar (progress updates)
- Audio: LiveKit or Pipecat backend for browser-based voice

#### CLI Surface (`surfaces/cli_surface.py`)

- Status line updates
- Refined transcript confirmation before send

---

## Prompt Engineering

### Refine System Prompt

```
You are an input refinement engine. Restructure messy spoken/typed input into
a clear, actionable prompt.

Rules:
1. Preserve original intent exactly
2. Resolve pronouns using conversation context (intent_history)
3. Expand vague references ("that thing" → specific noun)
4. Output ONLY the refined prompt. No preamble.

Conversation context: {intent_history}
Raw input: {raw_input}
```

### Distill System Prompt

```
You are a progress update generator. Given the agent's streaming output so
far and the user's original request, produce ONE natural-sounding update.

Rules:
1. ONE sentence. Conversational. Like a colleague updating you.
2. If still figuring out: "Looking into it..." / "Checking..."
3. If found something: "Found it — [key finding]"
4. If going off-topic: output "DRIFT" (signal to steering engine)
5. If nothing useful yet: output null

User intent: {user_intent}
Agent output: {partial_output}
```

### Steer System Prompt

```
You are a drift detector for an AI agent. Determine if the agent is going
off-topic compared to what the user originally asked for.

User wanted: {user_intent}
Agent is talking about: {current_topic}

Rules:
1. If aligned: output null (no intervention)
2. If slightly off but productive: output null (let it continue)
3. If clearly off-topic: output a 1-sentence correction for the agent

Output: null | "Redirect: stay focused on [user_intent]. [Suggestion]"
```

---

## Data Flow

### Text Path (Phase 1)

```
User types/speaks → STT (if voice) → raw text
  → pre_gateway_dispatch hook
    → intermediary.refine(raw_text)
    → surface.send_refined(raw, refined)
    → event.text = refined  (replace for agent)
  → Agent processes refined prompt (existing)
  → Streaming response
    → intermediary.distill(partial_tokens)
      → surface.update_progress(summary)
    → intermediary.steer.check(partial_tokens)
      → if drift: agent.steer("Redirect: ...")
        (injected into next tool result, NO interruption)
  → Agent completes
    → surface.send_final(summary)
```

### Voice Path (Phase 2+)

```
User speaks in Discord VC
  → VoiceReceiver captures PCM (existing)
  → pcm_to_wav() → transcribe_audio() (existing)
  → raw transcript
    → intermediary.refine()
    → Agent processes
  → Streaming response
    → intermediary.distill() → text channel updates
    → intermediary.steer() → agent.steer() if drift
  → Agent completes
    → intermediary.summarize() → TTS → speak in VC
    → Meanwhile: TEN/Pipecat detects if user barges in
      → stop_speaking() → back to listening
```

### Barge-in Flow (Full Duplex)

```
Agent is speaking in VC (TTS audio playing)
  → Audio backend detects user speech (VAD + TEN Turn Detection)
  → stop_speaking() — cut TTS immediately
  → Agent pauses (similar to pause() on VoiceReceiver)
  → Listen to user input
  → User stops speaking (end-of-turn detected)
  → Refine + send to agent as steer message
  → Agent adjusts course mid-response
```

---

## Integration Points

### hermes-agent Changes (minimal)

| File | Change |
|------|--------|
| `hermes_cli/plugins.py` | Add `intermediary_*` hooks to `VALID_HOOKS` |
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

### New Files (this repo)

```
intermediary/
  __init__.py
  plugin.yaml
  config.py
  state.py
  refine.py
  distill.py
  steer.py          # Hooks into agent.steer(), does NOT reinvent
  hooks.py
audio/
  __init__.py
  base.py           # AudioBackend ABC
  ten_backend.py    # TEN Turn Detection integration
  pipecat_backend.py # Pipecat pipeline
  livekit_backend.py # LiveKit transport (browser)
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
```

---

## External Dependencies

| Dependency | Repo | License | What We Use It For |
|---|---|---|---|
| **hermes-agent** | [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | — | Plugin host, agent.steer(), hooks |
| **hermes-webui** | [ChonSong/hermes-webui](https://github.com/ChonSong/hermes-webui) | — | Extension host, browser UI |
| **discord.py** | [Rapptz/discord.py](https://github.com/Rapptz/discord.py) | MIT | Voice IO, edit_message |
| **TEN Framework** | [TEN-framework](https://github.com/ten-framework/ten-framework) | Open-source | Full-duplex turn detection |
| **TEN Turn Detection** | [HuggingFace](https://huggingface.co/TEN-framework/TEN_Turn_Detection) | Open-source | Yield-floor detection |
| **TEN VAD** | [HuggingFace](https://huggingface.co/TEN-framework/ten-vad) | Open-source | Voice activity detection |
| **Pipecat** | [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | BSD-2 | Concurrent STT+LLM+TTS pipeline |
| **LiveKit** | [livekit/agents](https://github.com/livekit/agents) | Apache-2 | WebRTC transport (browser voice) |
| **Langfuse** | [langfuse/langfuse](https://github.com/langfuse/langfuse) | MIT | Observability (optional) |

---

## Why These Frameworks?

### TEN Turn Detection (primary for turn-taking)

- Open-source model trained specifically for human-AI turn-taking
- Detects when the agent should yield the floor (user wants to speak)
- Runs locally, no API dependency
- Much better than simple VAD silence detection

### Pipecat Pipeline (primary for concurrent audio)

- `ParallelPipeline` runs STT, LLM, TTS concurrently
- Barge-in support: detect user speech → stop TTS
- Vendor-neutral: swap STT/LLM/TTS providers
- Open-source Python

### LiveKit (browser transport)

- WebRTC transport for browser-based voice
- Heavier dependency — only needed if WebUI voice is a priority
- Alternative: WebSocket audio streaming is simpler for MVP

### What We DON'T Need

| Framework | Why Not |
|---|---|
| **Vapi** | Closed-source SaaS, telephony-focused |
| **Retell** | Closed-source SaaS, telephony-focused |
| **Full LiveKit** | Overkill unless browser voice is priority 1 |

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

---

## Success Criteria Summary

See [ROADMAP.md](ROADMAP.md) for phase-by-phase human-verifiable success criteria.

Key principles:
- Human-verifiable (not just automated tests)
- Each phase has concrete "signup and check this works" criteria
- Steering uses `agent.steer()` (verified by checking tool result injection)
- Audio sublayer is plug-and-play (verified by swapping backends)
