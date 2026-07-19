# Intermediary Agent — Complete Implementation Plan

> LiveKit-based voice intermediary between human and Hermes. Single system prompt, no separate modules. Hermes runs as a separate API.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  USER                      LIVEKIT PIPELINE                             │
│  ─────────                 ────────────────                            │
│                                                                         │
│  speaks "um the docker    STT → text                                   │
│   thing?" ────────────→                                                 │
│                           Intermediary LLM (gpt-4o-mini)               │
│                           1. Refine: "Debug the Docker socket error"   │
│                           2. Call query_hermes(refined) → function     │
│                                                      ↕                  │
│                              GET /api/chat/stream → SSE deltas         │
│                           3. Distill each sentence                     │
│                           4. Handle barge-in → steer injection        │
│                           ↓                                             │
│  hears "Checking         TTS ← distilled text                          │
│   the logs..." ←────────                                               │
│                                                                         │
│  [user barges in]         VoicePipelineAgent.interrupt()               │
│  "no the OTHER error" → capture steer → POST /api/chat/steer           │
│                           Hermes adjusts course                          │
│                           New response → distill → TTS                  │
│                                                                         │
│  [Transcript UI — text mode also available]                            │
│  [You] "um the docker thing?"                                          │
│  [Refined] "Debug the Docker socket error"                             │
│  [Hermes] "First, let me check the Docker logs..."                     │
│  [Speaking] "Checking the logs. Found permission issue."               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Key Insight

The intermediary is a **thin LLM**, not three Python modules. All behaviors are encoded in the system prompt:

```python
INTERMEDIARY_SYSTEM_PROMPT = """You are the intermediary between the user and Hermes.

Your behaviors:
1. REFINE: When the user speaks in fragments or with vague references, clarify their 
   intent using conversation context before sending to Hermes.
2. DISTILL: When Hermes responds with long technical output, summarize it naturally 
   for speech.
3. STEER: When the user interrupts, capture their correction and inject it.

Rules:
- Preserve user intent exactly — never change what they are asking for
- Resolve pronouns using conversation history
- Keep distilled output to 1-2 sentences for natural speech
- If the user interrupts, stop speaking immediately and listen
- You do NOT do heavy reasoning — that is Hermes's job.
- After refining, call query_hermes with the refined prompt.

Conversation context:
{intent_history}
"""
```

## Components

### 1. VoicePipelineAgent (LiveKit built-in)

LiveKit's `VoicePipelineAgent` class handles:
- **STT**: Speech-to-text via Deepgram Nova-3
- **LLM**: The intermediary (gpt-4o-mini or similar)
- **TTS**: Text-to-speech via Cartesia Sonic-3
- **VAD**: Voice activity detection (is user speaking?)
- **Turn-taking**: When is the user done speaking?
- **Barge-in**: `session.interrupt()` stops TTS immediately
- **Echo cancellation**: Agent doesn't hear itself

### 2. Hermes via Function Calling

```python
from livekit.agents import function_tool

@function_tool
async def query_hermes(prompt: str) -> str:
    """Send a prompt to Hermes and return the response."""
    # POST /api/chat/start → stream_id
    # GET /api/chat/stream → SSE deltas
    # Buffer to sentence boundaries → distill → return
    ...
```

The intermediary LLM sees `query_hermes` as an available tool. When user says "um the docker thing?", the LLM:
1. Refines to "Debug the Docker socket permission error"
2. Calls `query_hermes("Debug the Docker socket permission error")`
3. Hermes streams back response
4. Each delta goes through DistillationBuffer → distill() → TTS

### 3. Distillation Buffer (1-4 char SSE → sentence boundary)

```python
class DistillationBuffer:
    def feed(self, delta: str) -> Optional[str]:
        self.buffer += delta
        if self._has_sentence_boundary(self.buffer):
            sentence = self.buffer.strip()
            self.buffer = ""
            return sentence
        return None
```

SSE deltas from Hermes are 1-4 characters. The LLM cannot rewrite sub-word tokens. Buffer accumulates until sentence boundary (`.`, `!`, `?`, `:`, `\n`, or safety yield >150 chars), then passes complete sentence to distill().

### 4. Steering via `agent.steer()` (Existing Hermes Mechanism)

When user interrupts, LiveKit's VAD triggers `session.interrupt()`. The captured text is forwarded to Hermes via `POST /api/chat/steer` (non-interrupting). Hermes applies at next tool boundary.

## Why Not TEN?

TEN Framework provides better turn-taking for hands-free group conversations. For a single-user agent with barge-in, LiveKit's built-in VAD + `session.interrupt()` is sufficient. TEN can be reconsidered later if turn-taking feels unnatural.

## Hermes Integration (Exact)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat/start` | POST | `{session_id, message}` → `{stream_id}` |
| `/api/chat/stream` | GET | `?stream_id=...` → SSE deltas |
| `/api/chat/steer` | POST | `{session_id, text}` → `{accepted: bool}` |

### Steer Mechanism

```python
# streaming.py _handle_chat_steer():
cached = SESSION_AGENT_CACHE.get(session_id)
agent = cached[0]
accepted = agent.steer(text)
# → Text stashed in _pending_steer
# → Applied at next tool-result boundary with "User guidance:" marker
```

### SSE Stream Format

```
data: {"type": "delta", "content": "First, let me check"}
data: {"type": "tool_use", "tool": "read_file", "args": {"path": "/var/log/syslog"}}
data: {"type": "thinking", "content": "Let me think..."}
data: {"type": "error", "message": "Something went wrong"}
data: {"type": "done"}
```

## Phases

| Phase | Goal | Est. |
|-------|------|------|
| 1 | Text MVP with mock Hermes | ✅ Done |
| 2 | LiveKit voice pipeline | 4-6 hours |
| 3 | Real Hermes integration (with auth) | 1 hour |
| 4 | Discord bridge | 1 day |
| 5 | WebUI extension (text-only mode) | 1 day |

## File Structure

```
intermediary-agent/
├── intermediary/
│   ├── __init__.py
│   ├── voice_agent.py          # LiveKit VoicePipelineAgent wiring
│   ├── hermes_tools.py         # query_hermes function_tool
│   ├── hermes_client.py        # HTTP client for Hermes API
│   ├── distillation.py         # DistillationBuffer + distill()
│   └── events.py               # IntermediaryEvent schema (emotion-avatar ext)
├── audio/
│   ├── base.py                 # AudioBackend ABC
│   ├── livekit_native.py       # LiveKit built-in STT/TTS (default)
│   ├── discord_bridge.py       # Discord VC bridge (Phase 3)
│   └── mock_backend.py         # Mock for testing
├── webui/
│   ├── text_server.py          # FastAPI text server (Phase 1)
│   ├── templates/mvp.html      # Text MVP frontend
│   ├── static/mvp.css          # Dark theme
│   ├── static/mvp.js           # SSE streaming + demo mode
│   └── voice_extension.py      # LiveKit worker (Phase 2)
├── tests/
│   ├── conftest.py
│   ├── test_distillation.py
│   ├── test_steering.py
│   ├── test_hermes_client.py
│   ├── test_text_mvp.py
│   ├── test_live_integration.py
│   └── test_voice_agent.py     # Phase 2
├── PROGRESS.md
├── README.md
└── pyproject.toml
```

## Performance Requirements

| Metric | Target |
|--------|--------|
| STT latency | < 200ms |
| First Hermes chunk | < 1s |
| Distill per sentence | < 200ms |
| TTS latency | < 100ms |
| Barge-in response | < 200ms (VAD → stop TTS → capture steer) |
| End-to-end | < 2.5s (speak → hear first response) |

## Security & Privacy

- LiveKit WebRTC is encrypted (SRTP)
- Hermes API uses existing auth
- Session state stays in-memory
- No PII in logs

## Repo & Status

- **GitHub**: https://github.com/ChonSong/intermediary-agent
- **Local**: `/home/sc/intermediary-agent`
- **Phase**: 1 complete, Phase 2 next
