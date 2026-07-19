# Path C: Self-Hosted Voice Agent — DeepThink Analysis

## Loop 1 — Surface

**Problem:** Design a voice agent with zero third-party API dependencies (no LiveKit, no Deepgram, no Cartesia, no OpenAI).

**Initial answer:** Browser Web Speech API + local LLM (Ollama) + local STT/TTS (faster-whisper + Kokoro).

## Loop 2 — Explore

**Alternatives considered:**

| Alternative | Quality | Privacy | Complexity | Verdict |
|-------------|---------|---------|------------|---------|
| Web Speech API only | Low (robotic TTS) | ❌ audio to Google | Low | Prototype only |
| Local STT/TTS + browser transport | High | ✅ Full | Medium | **Production path** |
| LiveKit (commercial) | High | ❌ data leaves | High | Too expensive |
| Whisper.cpp + browser TTS | Medium | ✅ Full | Low | Good middle ground |

**Edge cases discovered:**
- Web Speech API TTS is clearly robotic, unusable for production feel
- faster-whisper needs GPU for real-time; CPU = 3-5s latency
- Kokoro TTS needs ~2GB RAM, runs on CPU
- WebSocket audio streaming requires custom server
- Barge-in (interrupting agent while speaking) needs VAD
- Echo cancellation needs WebRTC AEC

## Loop 3 — Challenge

**Assumptions challenged:**

1. **"Browser Web Speech API is easiest"** — True for prototype, false for quality. TTS sounds like a 2005 GPS navigation system.

2. **"No third-party APIs = free"** — Misleading. Local models need GPU/CPU compute. Cloud APIs are cheaper at low volume.

3. **"Self-hosted = private"** — Only if ALL components are local. Web Speech API sends audio to Google. So it's not private despite being "browser-native."

4. **"Hermes does the reasoning so intermediary is thin"** — True, but voice adds timing constraints. The intermediary must produce first TTS chunk within ~2s or user perceives lag.

## Loop 4 — Synthesize (Final Architecture)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                         USER'S BROWSER                                   │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  Voice UI (vanilla JS)                                          │   │
│   │  - mic button → getUserMedia() → audio stream                   │   │
│   │  - WebSocket → send/receive PCM frames                          │   │
│   │  - WebRTC AEC (browser built-in echo cancellation)              │   │
│   │  - <audio> element → play received TTS frames                   │   │
│   │  - Visual: live transcript with speaker colors                  │   │
│   └───────────────────────────┬─────────────────────────────────────┘   │
│                               │                                         │
│                         WebSocket (WSS)                                  │
│                         PCM audio frames                                │
│                         text/control messages                           │
│                               │                                         │
│                               ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                VOICE SERVER (Python, FastAPI)                    │   │
│   │                                                                  │   │
│   │  ┌────────────────────────────────────────────────────────────┐  │   │
│   │  │  Audio Receiver                                            │  │   │
│   │  │  - silero-vad → detect speech/silence/barge-in            │  │   │
│   │  │  - pydub → resample/normalize frames                      │  │   │
│   │  └────────────────────────────┬───────────────────────────────┘  │   │
│   │                               │                                  │   │
│   │                               ▼                                  │   │
│   │  ┌────────────────────────────────────────────────────────────┐  │   │
│   │  │  STT (faster-whisper, local)                              │  │   │
│   │  │  - continuous → text transcript                           │  │   │
│   │  │  - partial results for early LLM call start               │  │   │
│   │  └────────────────────────────┬───────────────────────────────┘  │   │
│   │                               │                                  │   │
│   │                               ▼                                  │   │
│   │  ┌────────────────────────────────────────────────────────────┐  │   │
│   │  │  Intermediary (Ollama, local)                             │  │   │
│   │  │  - System prompt: refine + distill + steer                │  │   │
│   │  │  - tool call → Hermes API → SSE deltas                   │  │   │
│   │  │  - DistillationBuffer → distill per sentence              │  │   │
│   │  └────────────────────────────┬───────────────────────────────┘  │   │
│   │                               │                                  │   │
│   │                               ▼                                  │   │
│   │  ┌────────────────────────────────────────────────────────────┐  │   │
│   │  │  TTS (Kokoro-82m, local)                                  │  │   │
│   │  │  - text → PCM audio frames                                │  │   │
│   │  │  - streaming: send frames as they're generated            │  │   │
│   │  └────────────────────────────┬───────────────────────────────┘  │   │
│   │                               │                                  │   │
│   │                               ▼                                  │   │
│   │  ┌────────────────────────────────────────────────────────────┐  │   │
│   │  │  Audio Sender                                              │  │   │
│   │  │  - WebSocket → send PCM frames to browser                 │  │   │
│   │  │  - barge-in: pause sending when VAD detects user speech    │  │   │
│   │  └────────────────────────────────────────────────────────────┘  │   │
│   │                                                                  │   │
│   └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Loop 5 — Converge

**Final component list (all local, no API keys):**

| Component | Library/Model | Purpose | Hardware |
|-----------|--------------|---------|----------|
| VAD | silero-vad | Speech/silence detection | CPU-only, 1MB |
| STT | faster-whisper (base) | Speech → text | CPU: 3-5s latency; GPU: <500ms |
| Intermediary | Ollama (qwen2.5:7b) | refine + distill + steer | CPU/GPU, 5GB RAM |
| TTS | Kokoro-82m | Text → audio | CPU: 2-3s; GPU: 300ms |
| Hermes | Existing API | Reasoning | Your existing setup |
| Transport | uvicorn + WebSocket | Audio + control | — |
| Browser API | getUserMedia + WebRTC AEC | Mic + speakers + AEC | Browser built-in |

**Total resources needed:**
- ~8GB RAM (Ollama 7B + Kokoro + Whisper)
- GPU optional (all works on CPU, GPU makes it real-time)
- ~5GB disk for models

## Implementation Phases

### Phase A: Prototype (Web Speech API, 30 min)

- Browser `webkitSpeechRecognition` → text
- POST to existing text server → SSE events
- `speechSynthesis` speaks distilled text
- **Goal:** Working voice in 30 min, prove the concept
- **Limitation:** Robotic TTS, not private

### Phase B: Local Models (2-3 hours)

- Start Ollama with qwen2.5:7b
- Start Kokoro TTS server
- Start faster-whisper
- Voice server wiring (VAD → STT → LLM → distill → TTS)
- WebSocket audio transport
- **Goal:** Production-quality voice, fully private

### Phase C: Polish (1 day)

- Barge-in (interrupt agent while speaking)
- Partial STT results for faster first-byte
- Streaming TTS (start speaking before full response)
- Echocancellation (WebRTC AEC in browser)
- Visual indicators (speaking/listening waveforms)

## Revised File Structure

```
intermediary-agent/
├── intermediary/
│   ├── text_intermediary.py    ✅ Text-only, tested
│   ├── hermes_client.py        ✅ HTTP/SSE, tested
│   ├── distillation.py         ✅ Buffer + distill, tested
│   ├── steering.py             ✅ Barge-in state, tested
│   ├── events.py               ✅ Event schema
│   └── voice/
│       ├── __init__.py
│       ├── server.py           # FastAPI WebSocket server (Phase B)
│       ├── vad.py              # silero-vad wrapper
│       ├── stt.py              # faster-whisper wrapper
│       ├── tts.py              # Kokoro wrapper
│       ├── llm.py              # Ollama intermediary LLM
│       └── pipeline.py         # Orchestrate STT→LLM→TTS
├── webui/
│   ├── text_server.py          ✅ FastAPI text + WebSocket
│   ├── templates/
│   │   ├── mvp.html            ✅ Text chat
│   │   └── voice.html          🎤 Voice interface
│   └── static/
│       ├── mvp.css             ✅ Dark theme
│       ├── mvp.js              ✅ SSE + demo mode
│       └── voice.js            🎤 WebSocket audio streaming
├── tests/
│   ├── test_distillation.py    ✅ 28 tests
│   ├── test_steering.py        ✅ 10 tests
│   ├── test_hermes_client.py   ✅ 5 tests
│   ├── test_text_mvp.py        ✅ 9 tests
│   └── test_voice.py           🎤 Voice pipeline tests
└── PROGRESS.md                 ✅ Tracking
```

## Key Decisions (Revisited)

**Why no LiveKit?**
- LiveKit requires commercial providers (Deepgram/OpenAI/Cartesia) for speech
- Local models give same quality, full privacy, zero ongoing cost
- One less dependency to manage

**Why not Web Speech API for production?**
- TTS quality is clearly robotic (user rejected it)
- Privacy concern (audio sent to Google)
- Inconsistent across browsers

**Why Ollama for intermediary instead of Hermes directly?**
- Intermediary must be fast (<2s first byte)
- Hermes can take 30s+ for complex tasks
- Ollama local: 200ms first token
- Hermes: reasoning + tools + memory (heavy)

**Why Kokoro for TTS?**
- Open-source, high quality voices
- Small model (~80MB)
- Runs on CPU at 2-3s for a sentence
- Natural sounding (neural TTS)

## Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Whisper CPU latency 3-5s | High | Start LLM call on partial STT result |
| Ollama RAM usage 5GB | Medium | Use smaller model (3b) or quantize |
| WebSocket audio complexity | Medium | Start with Phase A (Web Speech), migrate later |
| Barge-in detection false positives | Low | Tune VAD sensitivity, manual override |
| Echo (hearing itself) | Low | WebRTC AEC in browser handles it |
| Cross-browser compatibility | Low | WebSocket works everywhere; getUserMedia works everywhere |

## Definition of Done

Path C is complete when:
1. User clicks mic button in browser
2. Speaks a question
3. Browser shows live transcript as user speaks
4. Intermediary refines and sends to Hermes
5. Hermes response streams back
6. Intermediary distills to 1-2 sentences
7. TTS speaks the summary
8. User can interrupt (barge-in) while agent speaks
9. All works offline with no API keys
