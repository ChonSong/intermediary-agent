# Intermediary Agent — Complete Implementation Plan

> LiveKit-based intermediary that sits between user and Hermes. Thin voice interface, full text visibility, non-interrupting steer.

**Key insight**: The intermediary is an *adapter*. LiveKit handles audio timing/pacing. The intermediary just translates between Hermes SSE and LiveKit's expected formats.

**Three traps to avoid**:
1. **Barge-in trap**: POST /api/chat/steer *immediately* when VAD detects interrupt — NOT after SSE finishes
2. **Distillation buffer**: SSE deltas are 1-4 chars — too small for LLM rewriting. Must buffer to sentence boundary first.
3. **Testing trap**: Do NOT use Playwright to measure 200ms audio latency — use telemetry timestamps. Do NOT spin up full Hermes/LiveKit in pytest — use a mock SSE server.

---

## 1. Architecture (Corrected)

```
User ←→ (LiveKit WebRTC) ←→ Intermediary Agent ←→ (HTTP/SSE) ←→ Hermes
  ↕                                                          ↕
 Sees text transcript                                     Does the heavy lifting
 Hears distilled voice                                    runs the main agent
 Can barge-in / steer
```

- Hermes runs as a **separate API** (NOT a LiveKit function call). Zero changes to hermes-agent/hermes-webui.
- All three behaviors (refine/distill/steer) are encoded in the **system prompt** of a single lightweight intermediary LLM.
- LiveKit's `Synthesizer` accepts `AsyncIterable[str]` and handles sentence boundaries + audio queueing internally.
- Distillation needs its own buffer: SSE deltas are 1-4 chars, too small for LLM rewriting.

### Two Critical Implementation Traps

**Trap 1 — Barge-in Steer Timing**: POST `/api/chat/steer` must happen IMMEDIATELY when VAD detects interrupt, NOT after SSE ends. If SSE finishes, the run completes, and the steer fails with `fallback: "stream_dead"`.

**Trap 2 — Distillation Buffer**: SSE deltas are 1-4 characters. You cannot pass sub-word tokens to an LLM for rewriting. The intermediary buffers deltas until sentence boundary, then passes the complete sentence to the distillation LLM.

```python
async def hermes_stream_to_livekit(stream_id: str) -> AsyncIterable[str]:
    """Translate Hermes SSE to LiveKit's expected input format."""
    buffer = ""
    async for delta in hermes_client.stream_chat(stream_id):
        if is_steering_active():
            continue  # Drop stale deltas after barge-in
        buffer += delta
        if has_sentence_boundary(buffer):
            distilled = await distill(buffer)
            if distilled:
                yield distilled
            buffer = ""

await agent.session.say(hermes_stream_to_livekit(stream_id))
```

---

## 2. Hermes Integration (Exact Endpoints)

All three endpoints exist. Zero changes to hermes-agent/hermes-webui required.

| Endpoint | Method | Request | Response | Located at |
|----------|--------|---------|----------|------------|
| `/api/chat/start` | POST | `{session_id, message, profile?}` | `{stream_id}` | `routes.py:21240` (`_handle_chat_start`) |
| `/api/chat/stream` | GET | `?stream_id=...` | SSE stream | `routes.py` (`_handle_session_sse_stream`) |
| `/api/chat/steer` | POST | `{session_id, text}` | `{accepted: bool}` | `streaming.py:10296` (`_handle_chat_steer`) |

### `/api/chat/steer` Mechanism (Exact)
```python
# In streaming.py _handle_chat_steer():
cached = SESSION_AGENT_CACHE.get(session_id)
agent = cached[0]
accepted = agent.steer(text)  # Thread-safe, non-interrupting
# → Text stashed in _pending_steer
# → Applied at next tool-result boundary with "User guidance:" marker
# → Agent adjusts course WITHOUT interruption
```

### SSE Stream Format (Exact)
```
data: {"type": "delta", "content": "First, let me check"}
data: {"type": "tool_use", "tool": "read_file", "args": {"path": "/var/log/syslog"}}
data: {"type": "thinking", "content": "Let me think..."}
data: {"type": "error", "message": "Something went wrong"}
data: {"type": "done"}
```

---

## 3. Data Flow

### Normal Turn
```
1. User speaks → LiveKit STT commits text
2. Intermediary refines (system prompt — single LLM call)
3. HTTP POST /api/chat/start → {stream_id}
4. HTTP GET /api/chat/stream → SSE deltas
5. Buffer to sentence → distill → yield to LiveKit Synthesizer
6. LiveKit handles sentence boundaries + TTS + WebRTC playback
7. User hears distilled response
```

### Barge-in Turn (Corrected Sequence)
```
1. Agent is speaking TTS (Hermes SSE still streaming)
2. User speaks → LiveKit VAD detects
3. IMMEDIATELY: session.stop_speaking() + POST /api/chat/steer
   (while Hermes is still running — NOT after SSE ends)
4. Set steer_active = true → drop stale SSE deltas
5. When agent applies steer at tool boundary → clear steer_active
6. Resume distillation from new response
```

---

## 4. Barge-in State Machine

```
LISTENING → user speech → SPEAKING → user barge-in → STALE → Hermes finishes → INJECT steer → SPEAKING
```

| State | Entry Condition | Behavior |
|-------|----------------|----------|
| LISTENING | Agent idle | Accept user speech → refine → POST /api/chat/start → SPEAKING |
| SPEAKING | Hermes streaming | Buffer deltas → distill → yield → TTS plays |
| STALE | VAD detects user speech while TTS playing | stop_speaking() + POST /api/chat/steer + drop deltas |
| INJECT | Hermes finishes current step | steer already POSTed; wait for new response → SPEAKING |

### Generation ID Tracking
To handle stale chunks after barge-in, increment a per-session counter. Each delta check compares its generation to the current generation — stale deltas are dropped.

---

## 5. File Structure

```
intermediary-agent/
├── README.md
├── PLAN.md
├── ROADMAP.md
├── INTEGRATION.md
├── pyproject.toml
├── intermediary/
│   ├── __init__.py
│   ├── agent.py                    # LiveKit Agent subclass
│   ├── hermes_client.py            # HTTP client for Hermes API
│   ├── distillation.py             # Buffer + distill logic
│   ├── steering.py                 # Barge-in capture + injection
│   ├── session.py                  # Session state (generation counter, steer_active)
│   └── prompts.py                  # System prompt templates
├── audio/
│   ├── base.py                     # AudioBackend ABC
│   ├── livekit_native.py           # LiveKit built-in STT/TTS (default)
│   ├── ten_backend.py              # TEN Turn Detection
│   ├── pipecat_backend.py          # Pipecat concurrent pipeline
│   └── discord_bridge.py           # Discord VC bridge
├── webui/
│   ├── app.py                      # FastAPI transcript UI
│   ├── static/
│   │   ├── transcript.js           # LiveKit transcription display
│   │   └── styles.css
│   └── templates/
│       └── index.html
├── tests/
│   ├── conftest.py                 # Mock Hermes server, test fixtures
│   ├── test_distillation.py        # Sentence buffer + distill unit tests
│   ├── test_steering.py            # Barge-in state machine unit tests
│   ├── test_hermes_client.py       # SSE parsing unit tests
│   ├── test_agent.py               # LiveKit agent integration test (mock server)
│   ├── test_transcript_ui.py       # Frontend transcript display test
│   └── test_e2e.py                 # Full E2E with real servers + video
├── test-evidence/
│   ├── videos/                     # Playwright video recordings
│   └── screenshots/
└── scripts/
    ├── dev.sh                      # Run locally
    └── doctor.sh                   # Self-diagnostic
```

---

## 6. Test Strategy (Corrected)

### The Mocking Blind Spot

Testing real-time audio timing with Playwright or spinning up full Hermes/LiveKit instances inside pytest fixtures leads to:
- `port already in use` errors
- Asynchronous deadlocks between WebRTC tasks and HTTP tasks
- WebRTC renegotiation flakes
- Browser mic-permission sandboxing

**The Fix**: Build test harnesses BEFORE the complex components. Use deterministic mock servers. Separate logic testing from timing testing.

### Three-Tier Testing (Revised)

| Tier | What | Tool | Runs Against |
|------|------|------|--------------|
| **1. Deterministic Logic** | State machine transitions, distillation buffer, refinement, SSE parsing | pytest | Nothing (pure Python) |
| **2. Mocked Integration** | Full pipeline flow, barge-in timing, steer injection | pytest | Mock Hermes server (`httpx` + FastAPI/Sanic mimicking SSE) |
| **3. E2E + Telemetry** | Real servers, real audio, real timing | Playwright + `time.perf_counter()` logs | Real LiveKit + Real Hermes |

### Tier 1: Deterministic Logic (Zero External Dependencies)

```python
# Test refinement
assert refine("um the docker thing?", intent_history=["Docker error"]) \
    == "Debug the Docker permission error"

# Test distillation buffer
buf = DistillationBuffer()
assert buf.feed("The ") is None
assert buf.feed("doc") is None
assert buf.feed("ker logs.") == "Checking the logs."

# Test barge-in state machine
sm = BargeInStateMachine()
assert sm.state == LISTENING
sm.on_user_speech("hello")
assert sm.state == SPEAKING
sm.on_vad_detect()  # barge-in
assert sm.steer_active is True
assert sm.pending_steer == "no wait"
sm.on_hermes_finish()
assert sm.state == INJECT
```

### Tier 2: Mocked Integration (Mock Hermes, Real-ish LiveKit)

Build a **lightweight mock HTTP server** in the test suite:

```python
# conftest.py
from fastapi import FastAPI
import asyncio

def make_mock_hermes(response_text: str, chunk_delay: float = 0.05):
    """Return a FastAPI app that mimics Hermes /api/chat SSE stream."""
    app = FastAPI()
    
    @app.post("/api/chat")
    async def chat():
        async def gen():
            for char in response_text:
                yield f"data: {{\"type\": \"delta\", \"content\": \"{char}\"}}\n\n"
                await asyncio.sleep(chunk_delay)
            yield f"data: {{\"type\": \"done\"}}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    
    @app.post("/api/chat/steer")
    async def steer(body: dict):
        return {"accepted": True}
    
    return app

# tests/test_agent.py
async def test_barge_in_stops_tts_before_sse_ends():
    mock = make_mock_hermes("First, let me check the Docker logs. " * 50, chunk_delay=0.1)
    async with TestClient(mock) as client:
        agent = IntermediaryAgent(hermes_url=client.base_url)
        # Start Hermes stream (simulated 5-second response)
        # User speaks
        await agent.on_user_speech("hello")
        await asyncio.sleep(0.3)  # TTS starts
        # User barges in
        t0 = time.perf_counter()
        await agent.on_user_speech("no wait")
        # Verify steer POSTed BEFORE SSE ends (which takes ~5s)
        await asyncio.sleep(0.05)
        assert agent.steer_posted_before_sse_end()
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.5  # Steer happened in <500ms, not >5s
```

**Benefits**: No port conflicts. No deadlocks. No WebRTC renegotiation. Fully deterministic chunk delays. Runs in CI without any external services.

### Tier 3: E2E + Telemetry (Real Servers, Video, Timing Logs)

For E2E, use **real LiveKit + real Hermes**, but separate UI validation from timing measurement:

```python
# tests/test_e2e.py
async def test_full_conversation_with_barge_in(browser):
    page = await browser.new_page()
    await page.goto("http://localhost:8080")
    await page.click("#join-room")
    await page.context.grant_permissions(["microphone"])
    
    # Use Chromium flags for audio injection (no real mic needed)
    # --use-fake-device-for-media-stream
    # --use-file-for-fake-audio-capture=test-audio/docker-question.wav
    
    await inject_audio(page, "test-audio/docker-question.wav")
    
    # Verify UI shows refined text + Hermes response text
    await page.wait_for_selector(".intermediary-refined")
    await page.wait_for_selector(".hermes-raw")
    await page.wait_for_selector(".agent-speaking")
    
    # Barge in mid-response
    await asyncio.sleep(0.3)
    await inject_audio(page, "test-audio/steer-other-error.wav")
    
    # Verify steer appeared in transcript
    await page.wait_for_selector(".steer-event")
    
    # Timing is verified via telemetry logs (see below), NOT DOM scraping
```

### Telemetry for Timing (NOT Playwright DOM scraping)

For 200ms barge-in cut-off verification, **use structured telemetry logs** with high-resolution timestamps:

```python
# Inside the intermediary agent:
import time

class Telemetry:
    def log(self, event: str, **kwargs):
        print(json.dumps({
            "ts": time.perf_counter(),
            "event": event,
            **kwargs
        }), flush=True)

# In barge-in handler:
telemetry.log("vad_detect", room=room)
telemetry.log("stop_speaking_called", room=room)
telemetry.log("steer_posted", room=room)
telemetry.log("delta_dropped", room=room, generation=gen)
telemetry.log("new_response_detected", room=room)
```

Then test timing by analyzing logs:

```python
def test_barge_in_cutoff_under_200ms():
    logs = run_e2e_with_telemetry("test-audio/steer-other-error.wav")
    vad_ts = log_ts(logs, "vad_detect")
    stop_ts = log_ts(logs, "stop_speaking_called")
    cutoff_ms = (stop_ts - vad_ts) * 1000
    assert cutoff_ms < 200, f"TTS cutoff took {cutoff_ms}ms (target: <200ms)"
```

### Chromium Audio Injection Flags

For E2E voice testing without real mic:

```python
browser = await playwright.chromium.launch(
    args=[
        "--use-fake-device-for-media-stream",
        "--use-file-for-fake-audio-capture=test-audio/input.wav",
    ],
    record_video_dir="test-evidence/videos/",
)
```

**For real mic testing (manual)**: Use virtual audio loopbacks (`snd-aloop` on Linux, BlackHole/VB-Cable on Mac/Windows).

---

## 7. Async State Synchronization (Crucial for Barge-in)

The intermediary has two concurrent async loops:
1. **LiveKit WebRTC tasks** — audio I/O, VAD, TTS playback
2. **Hermes HTTP/SSE tasks** — receiving text deltas

When VAD triggers barge-in, state must be mutated **instantly** across these loops without blocking.

### Solution: asyncio.Event + Per-Session State Lock

```python
class SessionState:
    def __init__(self):
        self.steer_active = asyncio.Event()  # Set on barge-in
        self.pending_steer: str | None = None
        self.generation: int = 0
        self._lock = asyncio.Lock()
    
    async def activate_steer(self, text: str):
        async with self._lock:
            self.pending_steer = text
            self.steer_active.set()
            self.generation += 1
    
    async def deactivate_steer(self):
        async with self._lock:
            self.steer_active.clear()
            self.pending_steer = None

# In SSE consumer loop:
async for delta in hermes_stream:
    if state.steer_active.is_set():
        continue  # Drop stale delta
    buffer += delta
    # ... distill, yield
```

The `asyncio.Event` is non-blocking and immediately visible across all async tasks in the same loop. No thread-safety needed because LiveKit and the SSE client both run on the same asyncio event loop.

---

## 8. Skills Per Phase

| Phase | Primary Skills | Why |
|-------|---------------|-----|
| 1.1–1.3 (Scaffold + Hermes client + LiveKit agent) | `agent-pipeline-intermediary` (reference patterns), LiveKit Agents SDK, `httpx` async streams | Core plumbing |
| 1.4 (Distillation buffer) | Deterministic text chunking, `pytest` | Isolated, testable logic |
| 1.5 (Transcript UI) | WebSocket broadcast, basic React | Internal agent state → browser |
| 1.6 (Barge-in + steering) | **`asyncio` concurrency primitives**, **`deep-think`** (state machine design), mock server pattern | **Most bug-prone phase** — async state sync + timing |
| 1.7 (Voice pipeline) | **Chromium media flags**, Audio profiles, LiveKit audio | Getting audio through browser sandbox |
| 1.8 (E2E + video) | **Structured log telemetry** (`time.perf_counter()`), `Playwright` context configs | Timing verification via logs, UI via video |

### DeepThink Usage

Use DeepThink for:
- Barge-in state machine design (async synchronization across LiveKit + Hermes loops)
- Distiller buffer sentence-boundary detection (edge cases: "Dr.", "e.g.", "U.S.A.")
- Mock server design (what delays/failures to simulate)

---

## 9. Session Plan (Revised)

| Session | Focus | Deliverable |
|---------|-------|-------------|
| **1** | Core scaffolding + mock Hermes server | Local lightweight mock Hermes server + basic LiveKit Agent connecting and reading simulated SSE text deltas |
| **2** | Text distillation + logic verification | Sentence boundary aggregator + Distillation LLM pipeline with full Tier 1 unit tests |
| **3** | State-steering engine (Phase 1.6 Part A) | VAD state machine logic. Code that instantly flags incoming text delta stream as "stale". Full Tier 2 mock integration tests |
| **4** | WebUI pipeline integration (Phase 1.6 Part B) | Point agent at real Hermes WebUI endpoints. Test live steering against real server |
| **5** | Voice + UI layer (Phases 1.5 + 1.7) | Wire real microphone/speaker via LiveKit. Spin up UI page showing status values. Chromium audio injection flags |
| **6** | Telemetry, verification + video (Phase 1.8) | Configure audio injection flags. Fire Playwright script. Output explicit timing logs. Screen recording of full E2E flow |

---

## 10. Configuration Reference

```yaml
# config.yaml

intermediary:
  enabled: true
  hermes_url: "http://localhost:3000"
  hermes_api_key: null
  features:
    refine: true
    distill: true
    steer: true
  thresholds:
    silence_ms: 1800
    max_steer_per_exchange: 1

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

livekit:
  url: "ws://localhost:7880"
  api_key: "devkey"
  api_secret: "secret"

frontend:
  host: "0.0.0.0"
  port: 8080
```

---

## 11. Performance Requirements

| Metric | Target | How to verify |
|--------|--------|---------------|
| Refinement | < 300ms | Tier 1 unit test |
| Distill per sentence | < 200ms | Tier 1 unit test |
| Stale delta drop | < 10ms per delta | Tier 1 unit test |
| Barge-in TTS cut-off | < 200ms | **Tier 3 telemetry log** (`time.perf_counter()`) |
| Steer POST before SSE ends | TRUE | **Tier 2 mock integration test`** (deterministic chunk delays) |
| End-to-end (speak → hear) | < 2.5s | Tier 3 E2E |

---

## 12. Security & Privacy

- LiveKit WebRTC is encrypted (SRTP)
- Hermes API uses existing auth
- Session state stays in-memory per session, never persisted
- No PII in INFO logs (only DEBUG + redacted)

---

## 13. Repo & Status

- **GitHub**: https://github.com/ChonSong/intermediary-agent
- **Local**: `/home/sc/intermediary-agent`
- **Phase**: 0 (Foundation) — building Phase 1 next

---

## 14. External Dependencies

| Dependency | Repo | Purpose |
|---|---|---|
| LiveKit Agents | [livekit/agents](https://github.com/livekit/agents) | Agent framework, WebRTC, plugins |
| Hermes WebUI | [ChonSong/hermes-webui](https://github.com/ChonSong/hermes-webui) | `/api/chat` SSE stream |
| Playwright | [playwright](https://playwright.dev/) | Video evidence for frontend/audio tests |
| Deepgram | [deepgram](https://deepgram.com/) | STT provider |
| Cartesia | [cartesia](https://cartesia.ai/) | TTS provider |
| TEN Framework | [TEN-framework](https://github.com/ten-framework/ten-framework) | Turn detection (Phase 2) |
| Pipecat | [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | Concurrent pipeline (Phase 4) |
