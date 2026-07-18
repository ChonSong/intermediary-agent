# Intermediary Agent — Complete Implementation Plan

> LiveKit-based intermediary that sits between user and Hermes. Thin voice interface, full text visibility, non-interrupting steer.

**Key insight**: The intermediary is an *adapter*. LiveKit handles audio timing/pacing. The intermediary just translates between Hermes SSE and LiveKit's expected formats.

**Two traps to avoid**:
1. **Barge-in trap**: POST /api/chat/steer *immediately* when VAD detects interrupt — NOT after SSE finishes
2. **Distillation buffer**: SSE deltas are 1-4 chars — too small for LLM rewriting. Must buffer to sentence boundary first.

---

## 1. LiveKit Stream Handling (Corrected)

LiveKit's `Synthesizer` accepts `AsyncIterable[str]` and handles sentence boundaries, chunking, and audio queueing internally. The intermediary just translates:

```python
async def hermes_stream_to_livekit(stream_id: str) -> AsyncIterable[str]:
    """Translate Hermes SSE stream into LiveKit's expected input format."""
    buffer = ""
    async for delta in hermes_client.stream_chat(stream_id):
        # Drop deltas if steer is pending
        if is_steering_active():
            continue
        
        buffer += delta
        
        # Only distill when we hit a complete sentence/clause
        if has_sentence_boundary(buffer):
            # Pass complete sentence to rewriting LLM
            distilled = await distill(buffer)
            
            # Yield clean, spoken-friendly text to LiveKit
            if distilled:
                yield distilled
            
            buffer = ""  # Reset for next sentence
```

LiveKit handles: sentence boundary detection, TTS chunking, audio frame queueing, WebRTC playback.

The intermediary's only job: translate SSE → produce clean `AsyncIterable[str]` for LiveKit.

---

## 2. Steer Timing (Corrected)

**Wrong (will fail)**:
```
user barges in → wait for SSE to finish → POST /api/chat/steer
```

**Correct (steer while agent is running)**:
```
user barges in → immediately POST /api/chat/steer → silently drop stale SSE deltas
```

Why: `/api/chat/steer` is designed to inject guidance into an *active* agent loop. If SSE finishes, the run is complete and the agent has terminated. The steer would fail with `fallback: "stream_dead"` or `fallback: "not_running"`.

After the steer is injected, the adapter silently drops all text deltas from the old context until the agent's next tool boundary applies the steer and starts generating the *new* response.

---

## 3. Hermes Integration

All three endpoints exist. **Zero changes to hermes-agent/hermes-webui required.**

| Endpoint | Method | Request | Response | Notes |
|----------|--------|---------|----------|-------|
| `/api/chat/start` | POST | `{session_id, message}` | `{stream_id}` | Start a run, get stream_id |
| `/api/chat/stream` | GET | `?stream_id=...` | SSE deltas (`data: {"type":"delta","content":"..."}`) | Stream response |
| `/api/chat/steer` | POST | `{session_id, text}` | `{accepted: bool, fallback?: str}` | Inject while active |

### Hermes Steer Endpoint (exact)
Located at `hermes-webui/api/streaming.py:10296` (`_handle_chat_steer`):

1. Looks up cached `AIAgent` from `SESSION_AGENT_CACHE`
2. Verifies stream is active for this session
3. Calls `agent.steer(text)` — thread-safe, non-interrupting
4. Agent loop applies steer to next tool result with `"User guidance:"` marker

If stream is dead/run finished, returns `{"accepted": false, "fallback": "stream_dead"}`.

**This is why barge-in steer must happen immediately — while the agent is still running.**

---

## 4. Data Flow

### Normal Turn
```
1. User speaks → LiveKit STT commits text
2. Intermediary refines (system prompt call)
3. HTTP POST /api/chat/start → {stream_id}
4. HTTP GET /api/chat/stream → SSE deltas
5. For each delta:
   a. Buffer until sentence boundary
   b. Distill via LLM Output Replacement
   c. yield distilled text
   d. LiveKit Synthesizer handles TTS chunking + audio queueing
6. User hears distilled response
```

### Barge-in Turn (Corrected Sequence)
```
1. Agent is speaking TTS (Hermes SSE still streaming)
2. User speaks → LiveKit VAD detects
3. Immediately:
   a. session.stop_speaking() — cuts TTS
   b. Capture user text as pending_steer
   c. HTTP POST /api/chat/steer — inject WHILE AGENT RUNNING
4. Adapter continues receiving SSE deltas
5. Adapter silently DROPS deltas from old context
6. Agent applies steer at next tool boundary
7. Agent generates new response
8. Adapter buffers new sentences → distill → yield → TTS
```

---

## 5. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  USER                      LIVEKIT AGENT (python)                       │
│  ─────────                 ──────────────────                            │
│                                                                         │
│  speaks "um the docker    STT → text                                    │
│   thing?" ────────────→                                                 │
│                           Intermediary refines → POST /api/chat/start   │
│                                                      → HERMES           │
│                           ← stream_id ──────────────────────────────    │
│                           GET /api/chat/stream                          │
│                           ← SSE deltas (1-4 chars each) ───────────     │
│                           Buffer to sentence → distill → yield          │
│                           ↓                                             │
│  hears "Checking         LiveKit Synthesizer handles:                   │
│   the logs..." ←────────  sentence boundaries + audio queueing          │
│                                                                         │
│  [Browser Transcript UI sees everything]                                │
│                                                                         │
│  user barges in:                                                        │
│  "no the OTHER error" → VAD → stop_speaking()                           │
│                           IMMEDIATELY: POST /api/chat/steer             │
│                                                      → HERMES           │
│                           Keep SSE open, DROP stale deltas              │
│                           Agent applies steer at next tool boundary     │
│                           New response → buffer → distill → yield → TTS │
│                                                                         │
│  [Hermes] "Ah, you meant the container startup error..."                │
│  [Speaking] "Adjusting — checking container startup..."                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Session Mapping

One LiveKit participant → one Hermes session.

```
LiveKit Room "room-abc"
  └─ Participant "user-sean"
       └─ hermes_session_id: "ses-xyz"
       └─ intent_history: ["Docker error", "file permissions"]
       └─ pending_steer: None → "no the OTHER error" → None (injected)
       └─ steer_active: false → true → false
```

Session created on participant connect. Destroyed on disconnect.

---

## 7. Distillation Buffer Implementation

SSE deltas from Hermes are 1-4 characters. Cannot pass sub-word to LLM for rewriting.

```python
def has_sentence_boundary(text: str) -> bool:
    """Detect sentence/clause boundary for distillation."""
    if not text:
        return False
    
    # End of sentence
    if text.rstrip().endswith(('.', '!', '?', ':')):
        return True
    
    # Clause boundary (comma + space) — yield if buffer is long enough
    if ', ' in text and len(text) > 40:
        return True
    
    # Newline boundary
    if '\n' in text:
        return True
    
    return False
```

Buffer accumulates deltas until boundary detected. Then:
1. Pass complete sentence to distillation LLM
2. Yield rewritten text to LiveKit
3. Reset buffer

---

## 8. Drift Detection (Clarification)

The intermediary does NOT autonomously detect "agent drift" and self-correct. All steering is user-initiated:

- User: "wait, also check auth.log" → captured as steer
- User: "no I meant the OTHER error" → captured as steer
- User: "skip that, just give me the command" → captured as steer

The intermediary just routes the steer to Hermes via POST /api/chat/steer while the agent is still running.

---

## 9. File Structure

```
intermediary-agent/
├── README.md
├── PLAN.md
├── ROADMAP.md
├── INTEGRATION.md
├── pyproject.toml
├── intermediary/
│   ├── __init__.py
│   ├── agent.py                    # LiveKit Agent
│   ├── hermes_client.py            # Hermes HTTP client
│   ├── distillation.py             # Buffer + distill logic
│   ├── steering.py                 # Barge-in capture + injection
│   ├── session.py                  # Session state
│   └── prompts.py                  # System prompt templates
├── audio/
│   ├── base.py
│   └── livekit_native.py           # Default backend
├── webui/
│   ├── app.py                      # FastAPI transcript UI
│   └── templates/
│       └── index.html
├── tests/
│   ├── test_distillation.py
│   ├── test_steering.py
│   ├── test_hermes_client.py
│   └── test_e2e.py
└── test-evidence/
    ├── videos/
    └── screenshots/
```

---

## 10. Test Strategy

### Playwright Video Evidence

Per user's request: frontend/voice tests record video to `test-evidence/videos/{phase}-{test}.webm`.

### Empirical Validation

Per `deep-think` skill: verification requires running the system, not reading code.

### Phase 1 Tests

| Test | Type | Evidence |
|------|------|----------|
| Refinement resolves pronouns | Unit | Terminal |
| Distillation buffers sub-word deltas correctly | Unit | Terminal |
| Barge-in triggers /steer IMMEDIATELY (before SSE ends) | Integration | Terminal |
| Steer injection returns `accepted: true` | Integration | Terminal |
| Video of full conversation flow | E2E | Screen recording |

---

## 11. Hermes WebUI Endpoints (Exact)

| File | Line | Function | Purpose |
|------|------|----------|---------|
| `api/routes.py` | ~21240 | `_handle_chat_start` | POST /api/chat/start |
| `api/routes.py` | ~12895 | `_handle_session_sse_stream` | GET /api/chat/stream |
| `api/streaming.py` | ~10296 | `_handle_chat_steer` | POST /api/chat/steer |

---

## 12. Performance Requirements

| Metric | Target |
|--------|--------|
| Refinement | < 300ms |
| Distill per sentence | < 200ms |
| Barge-in response | < 200ms (VAD → stop_speaking → POST steer) |
| Stale delta drop | < 10ms per delta |
| End-to-end (speak → hear response) | < 2.5s |

---

## 13. Security & Privacy

- LiveKit WebRTC is encrypted (SRTP)
- Hermes API uses existing auth
- Session state stays in-memory, never persisted
- No PII in INFO logs

---

## 14. Repo & Status

- **GitHub**: https://github.com/ChonSong/intermediary-agent
- **Local**: `/home/sc/intermediary-agent`
- **Phase**: 0 (Foundation) — building Phase 1 next
