# Intermediary Agent — Integration Points

> File paths, API endpoints, and configuration for integrating with Hermes, LiveKit, and external services.

---

## Architecture Summary

The intermediary is a **LiveKit Agent** (Python) that connects to Hermes via the existing **WebUI HTTP API**. No changes to hermes-agent or hermes-webui are required for Phase 1.

```
User ←→ (LiveKit WebRTC) ←→ Intermediary Agent ←→ (HTTP/SSE) ←→ Hermes WebUI
```

---

## Hermes WebUI Integration

### Endpoints Used

| Endpoint | Method | Purpose | Phase |
|----------|--------|---------|-------|
| `/api/sessions` | POST | Create new Hermes session | 1 |
| `/api/sessions` | GET | List active sessions | 1 |
| `/api/chat` | POST | Send message, receive SSE stream | 1 |
| `/api/chat` | POST | Inject steer (as next user message) | 1 |
| `/api/settings` | GET | Get session settings | 6 |

### SSE Stream Format

```
data: {"type": "delta", "content": "First, let me check"}

data: {"type": "tool_use", "tool": "read_file", "args": {"path": "/var/log/syslog"}}

data: {"type": "thinking", "content": "Let me think about this..."}

data: {"type": "error", "message": "Something went wrong"}

data: {"type": "done"}
```

### Hermes Response Types

| Type | What to Do | Distill? |
|------|-----------|----------|
| `delta` | Pass to distillation → TTS → transcript UI | Yes |
| `tool_use` | Show "Using tool: X" in transcript | No (suppress) |
| `thinking` | Suppress from TTS, optionally show in transcript | No |
| `error` | Speak error message, show in transcript | Yes |
| `done` | Check for pending steer, cleanup | No |

### Hermes Session Lifecycle

```
1. POST /api/sessions → {"session_id": "ses-xyz-789"}
2. POST /api/chat {"message": "...", "session_id": "ses-xyz-789"} → SSE stream
3. Multiple messages sent to same session_id
4. Session persists until timeout or explicit cleanup
```

### Hermes API Auth

```python
# If Hermes has auth enabled:
headers = {"Authorization": f"Bearer {api_key}"}

# If no auth (default for local):
headers = {}
```

---

## LiveKit Integration

### LiveKit Agent Lifecycle

```
1. Room created (via LiveKit server)
2. Participant connects (user joins via browser)
3. IntermediaryAgent.on_enter() → create Hermes session
4. User speaks → STT → user_speech_committed event
5. Agent.on_user_speech_committed() → refine → Hermes API
6. Hermes streams → distill → TTS
7. User barges in → stop_speaking() → capture steer
8. Hermes finishes → inject pending steer
9. User disconnects → on_leave() → cleanup session
```

### LiveKit Events Used

| Event | Handler | Purpose |
|-------|---------|---------|
| `user_speech_committed` | `on_user_speech_committed` | STT text ready → refine + send to Hermes |
| `agent_speech_committed` | `on_agent_speech_committed` | TTS text ready → forward to UI |
| `TranscriptionReceived` | Forward to UI | Full visibility |
| `ParticipantConnected` | `on_participant_connected` | Create Hermes session |
| `ParticipantDisconnected` | `on_participant_disconnected` | Cleanup |
| `RoomDisconnected` | `on_room_disconnected` | Cleanup |

### LiveKit Transcription Events

LiveKit publishes `TranscriptionReceived` events containing both user and agent text. Structure:

```json
{
    "participant_identity": "user-sean",
    "text": "um the docker thing?",
    "is_local": true,
    "timestamp": 1700000000
}
```

```json
{
    "participant_identity": "agent-intermediary",
    "text": "Looking into the Docker permission error",
    "is_local": false,
    "timestamp": 1700000005
}
```

These are forwarded to the frontend via WebSocket for the transcript UI.

### LiveKit LLM Output Replacement

LiveKit's `LLM Output Replacement` recipe intercepts text before TTS:

```python
from livekit.agents import llm

class DistillationFilter(llm.Modification):
    async def modify(self, text, context):
        # Summarize text for natural speech
        return distilled_text

# Register with agent
agent = IntermediaryAgent(
    llm=llm.with_output_replacement(
        DistillationFilter()
    )
)
```

### LiveKit Configuration

```bash
# Local development
livekit-server --dev

# Or LiveKit Cloud (production)
# Set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
```

### LiveKit Room Configuration

```python
# In agent.py
room_options = RoomOptions(
    enable_audio=True,
    enable_video=False,  # Audio only for now
    empty_timeout=300,   # 5 min empty room timeout
)
```

---

## Audio Sublayer Integration

### AudioBackend ABC

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

### Backend Implementations

| Backend | Transport | Phase | Config |
|---------|-----------|-------|--------|
| `LiveKitNativeAudio` | WebRTC | 1 | `audio.backend: livekit` |
| `TENAudioBackend` | WebRTC + TEN Turn Detection | 2 | `audio.backend: ten` |
| `PipecatAudioBackend` | WebSocket | 4 | `audio.backend: pipecat` |
| `DiscordAudioBridge` | Discord VC | 3 | `audio.backend: discord` |

### TEN Turn Detection Integration

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

### Audio Config

```yaml
# config.yaml
audio:
  backend: livekit    # livekit | ten | pipecat | discord
  barge_in: true
  turn_detection: true
  stt:
    provider: deepgram  # deepgram | openai | google
    model: nova-3
  tts:
    provider: cartesia  # cartesia | openai | elevenlabs
    model: sonic-3
```

---

## Frontend Integration

### WebSocket Protocol

LiveKit transcript events → intermediary forwards to frontend:

```json
{
    "type": "transcript",
    "speaker": "user",
    "text": "um the docker thing?",
    "timestamp": 1700000000
}
```

```json
{
    "type": "transcript",
    "speaker": "hermes_raw",
    "text": "First, let me check the Docker logs...",
    "timestamp": 1700000005
}
```

```json
{
    "type": "transcript",
    "speaker": "agent_speaking",
    "text": "Checking the Docker logs...",
    "timestamp": 1700000006
}
```

```json
{
    "type": "steer",
    "text": "no the OTHER error",
    "timestamp": 1700000010
}
```

### Frontend Stack

- **React** or vanilla JS (keep it simple)
- **LiveKit Client SDK** for WebRTC connection
- **WebSocket** for transcript events
- **CSS** for styling (dark theme to match WebUI)

### Frontend Layout

```
┌─────────────────────────────────────────────────────┐
│  Intermediary Agent — Live Transcript               │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  [You] "um the docker thing?"                   │ │
│  │  [Intermediary] → "Debug the Docker permission  │ │
│  │                    error"                       │ │
│  │  [Hermes] "First, let me check the logs..."     │ │
│  │  [Speaking] "Checking the logs..."              │ │
│  │  ...                                            │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ ┌────────┐ │
│  │ 🎙 Mute  │  │ ⏹ Leave  │  │ 🔄 Clear │ │ ⚙      │ │
│  └──────────┘  └──────────┘  └──────────┘ └────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## Session Mapping

### LiveKit ↔ Hermes Session

```
LiveKit Room "room-abc-123"
  └─ Participant "user-sean"
       └─ SessionState
            ├─ hermes_session_id: "ses-xyz-789"
            ├─ intent_history: ["Docker error", "file permissions"]
            ├─ current_topic: "Docker socket permissions"
            ├─ current_generation: 4
            └─ pending_steer: None
```

### Session Manager

```python
class SessionManager:
    """Maps LiveKit participants to Hermes sessions."""
    
    def __init__(self, hermes_url: str):
        self.hermes_client = HermesClient(hermes_url)
        self.sessions: dict[str, SessionState] = {}  # room+participant -> state
    
    async def create_session(
        self, room: str, participant: str
    ) -> SessionState:
        """Create Hermes session for new participant."""
        hermes_session_id = await self.hermes_client.create_session()
        state = SessionState(
            room=room,
            participant_identity=participant,
            hermes_session_id=hermes_session_id,
            hermes_url=self.hermes_client.base_url,
        )
        key = self._key(room, participant)
        self.sessions[key] = state
        return state
    
    def get_session(
        self, room: str, participant: str
    ) -> SessionState | None:
        """Get session for participant."""
        return self.sessions.get(self._key(room, participant))
    
    def _key(self, room: str, participant: str) -> str:
        return f"{room}:{participant}"
```

---

## Configuration

### Full Configuration Reference

```yaml
# config.yaml

# Intermediary configuration
intermediary:
  enabled: true
  hermes_url: "http://localhost:3000"  # Hermes WebUI URL
  hermes_api_key: null                 # Hermes API key (if auth enabled)
  
  # Model configuration
  models:
    intermediary: "openai/gpt-4o-mini"  # Lightweight model for intermediary
    distillation: "openai/gpt-4o-mini"  # Model for distillation
  
  # Feature toggles
  features:
    refine: true      # Enable input refinement
    distill: true     # Enable output distillation
    steer: true       # Enable barge-in steering
  
  # Thresholds
  thresholds:
    drift_confidence: 0.7  # NOT USED — steering is user-initiated
    silence_ms: 1800       # For voice input
    max_steer_per_exchange: 1
  
  # Audio configuration
  audio:
    backend: livekit    # livekit | ten | pipecat | discord
    barge_in: true
    turn_detection: true
    stt:
      provider: deepgram
      model: nova-3
    tts:
      provider: cartesia
      model: sonic-3
  
  # Platform-specific
  platforms:
    discord:
      edit_interval_ms: 500
      max_update_length: 1800
    webui:
      stream_mode: "sentence"
    cli:
      spinner: true

# LiveKit configuration
livekit:
  url: "ws://localhost:7880"
  api_key: "devkey"
  api_secret: "secret"

# Frontend configuration
frontend:
  host: "0.0.0.0"
  port: 8080
  cors_origins: ["http://localhost:3000", "http://localhost:8080"]
```

---

## External Dependencies

### Python Packages

```toml
# pyproject.toml
[project]
dependencies = [
    "livekit-agents>=0.12.0",
    "livekit-plugins-deepgram>=0.6.0",    # STT
    "livekit-plugins-cartesia>=0.4.0",    # TTS
    "livekit-plugins-openai>=0.10.0",     # OpenAI LLM
    "livekit-plugins-silero>=0.7.0",      # VAD
    "aiohttp>=3.9.0",                     # HTTP client for Hermes API
    "fastapi>=0.110.0",                   # Frontend server
    "uvicorn>=0.27.0",                    # ASGI server
    "websockets>=12.0",                   # WebSocket for frontend
    "pydantic>=2.6.0",                    # Config validation
    "python-dotenv>=1.0.0",               # Env var loading
]

[project.optional-dependencies]
ten = ["torch>=2.0.0", "transformers>=4.30.0"]  # TEN Turn Detection
pipecat = ["pipecat-ai>=0.0.0"]                  # Pipecat pipeline
discord = ["discord.py[voice]>=2.3.0"]           # Discord bridge
test = ["pytest>=8.0.0", "playwright>=1.40.0"]   # Testing
```

### External Services

| Service | Provider | Purpose | Phase |
|---------|----------|---------|-------|
| LiveKit Server | [livekit/livekit-server](https://github.com/livekit/livekit-server) | WebRTC server | 1 |
| Deepgram | [deepgram](https://deepgram.com/) | STT | 1 |
| Cartesia | [cartesia](https://cartesia.ai/) | TTS | 1 |
| OpenAI | [openai](https://openai.com/) | Intermediary LLM | 1 |
| Hermes WebUI | [ChonSong/hermes-webui](https://github.com/ChonSong/hermes-webui) | Agent API | 1 |
| TEN Turn Detection | [HuggingFace](https://huggingface.co/TEN-framework/TEN_Turn_Detection) | Turn detection | 2 |
| Pipecat | [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | Concurrent pipeline | 4 |
| Discord | [discord.py](https://github.com/Rapptz/discord.py) | Voice channel bridge | 3 |

---

## Development Workflow

### Local Development

```bash
# Terminal 1: Start LiveKit server
livekit-server --dev

# Terminal 2: Start Hermes WebUI (if not already running)
cd /home/sc/repos/hermes-webui
python3 bootstrap.py

# Terminal 3: Start intermediary agent
cd /home/sc/intermediary-agent
python3 -m intermediary.agent

# Terminal 4: Start frontend
cd /home/sc/intermediary-agent
python3 -m webui.app

# Browser: Open http://localhost:8080
```

### Testing

```bash
# Unit tests
pytest tests/test_refinement.py tests/test_distillation.py -v

# Integration tests (requires LiveKit + Hermes running)
pytest tests/test_agent.py -v

# Frontend tests with video evidence
pytest tests/test_transcript_ui.py --video=on

# E2E test
pytest tests/test_e2e.py --video=on
```

### Self-Diagnostic

```bash
# Check all components are working
./scripts/doctor.sh

# Expected output:
# ✓ LiveKit server reachable
# ✓ Hermes WebUI reachable
# ✓ STT provider (Deepgram) configured
# ✓ TTS provider (Cartesia) configured
# ✓ Intermediary LLM (OpenAI) configured
# ✓ Frontend server running
```

---

## Key Hermes-Agent Code Paths (for reference)

| Purpose | File | Symbol |
|---------|------|--------|
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

---

## Key Hermes-WebUI Code Paths (for reference)

| Purpose | File | What to Add |
|---|---|---|
| Extension hookup | `static/extension_settings.js` | Register intermediary extension |
| Composer UI | `static/index.html` | Two-pane composer markup |
| Voice pipeline | `static/boot.js` | Intermediary intercept after STT |
| Agent streaming | `static/ui.js` | Token-level intermediary events |
| Settings UI | `static/panels.js` | Intermediary preferences/toggles |
| Backend API | `api/extensions.py` | `/api/intermediary/stream` SSE |
| Settings persistence | `api/config.py` | `intermediary:` config section |

---

## Barge-in State Machine

```
┌─────────────┐
│  LISTENING  │ ←─────────────────────────────────────┐
└──────┬──────┘                                        │
       │                                               │
       │ user speech committed                          │
       │ (refined → Hermes API)                         │
       ↓                                               │
┌─────────────┐                                        │
│  SPEAKING   │                                        │
│  (Hermes    │                                        │
│   streaming │                                        │
│   → TTS)    │                                        │
└──────┬──────┘                                        │
       │                                               │
       │ user barge-in detected                        │
       │ (stop_speaking + capture steer)               │
       ↓                                               │
┌─────────────┐                                        │
│  STALE      │                                        │
│  (Hermes    │                                        │
│   still     │                                        │
│   streaming │                                        │
│   but TTS   │                                        │
│   stopped)  │                                        │
└──────┬──────┘                                        │
       │                                               │
       │ Hermes finishes current step                  │
       │                                               │
       ↓                                               │
┌─────────────┐     has pending steer                  │
│  INJECT     │ ─────────────────────────────────────→ │
│  (send steer│     no pending steer                   │
│   to Hermes)│                                        │
└──────┬──────┘                                        │
       │                                               │
       │ steer sent → back to SPEAKING                 │
       │                                               │
       └───────────────────────────────────────────────┘
```

---

## Performance Requirements

| Metric | Target | Rationale |
|--------|--------|-----------|
| STT latency | < 200ms | LiveKit STT is fast |
| Refinement | < 300ms | Single LLM call (system prompt) |
| First Hermes chunk | < 1s | Network + Hermes init |
| Distill per chunk | < 200ms | Fast model, small input |
| TTS latency | < 100ms | Streaming TTS |
| Barge-in response | < 200ms | User speaks → agent stops |
| Echo cancellation | Built-in | LiveKit handles |
| Turn detection | < 100ms | LiveKit built-in |
| End-to-end (speak → hear response) | < 2s | Total loop latency |

---

## Security & Privacy

- LiveKit WebRTC is encrypted (SRTP)
- Hermes API calls use existing auth (API key / token)
- Conversation state (intent_history) stays in-memory per session, never persisted
- Transcript UI is local (served by intermediary FastAPI, not public)
- No PII in intermediary logs at INFO level (only DEBUG + redacted)
