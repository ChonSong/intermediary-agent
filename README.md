# Intermediary Agent

> A LiveKit-based voice intermediary that sits between you and Hermes. Refines messy input, distills verbose output, handles barge-in steering. All visible as text, all conversational by voice.

---

## The Problem

| This... | ...is tiring |
|---------|-------------|
| "um so like the docker thing I was talking about earlier? the error?" | → You have to clarify 3 times |
| The agent gives you a 5-paragraph explanation when you wanted the command | → You gave up reading |
| The agent starts explaining Docker history instead of fixing your issue | → You have to interrupt and restart |

## The Solution

A **LiveKit agent** that is the ears and mouth between you and Hermes. It does NOT reason — that Hermes does. The intermediary just clarifies, distills, and routes.

**1. Refine** your messy spoken/typed input into a clear, actionable prompt

> "um the docker thing?" → "Debug the Docker socket permission error from the previous command"

**2. Distill** Hermes' verbose streaming output into natural, concise speech

> Hermes streams 3 paragraphs → Intermediary speaks: "Found 3 issues. Here's the main one:"

**3. Steer** Hermes when you interrupt — mid-turn, without stopping the conversation

> You barge in: "no the OTHER error" → Intermediary immediately POSTs `/api/chat/steer` while Hermes is still running

**4. Watch everything** — full text transcript in the browser while you converse by voice

## How It Works

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
│                           HERMES: creates run → returns {stream_id}     │
│                           GET /api/chat/stream                          │
│                           ← SSE deltas (1-4 chars each)                 │
│                           Buffer to sentence → distill → yield          │
│                           ↓                                             │
│  hears "Checking         LiveKit Synthesizer                            │
│   the logs..." ←────────  handles sentence boundaries + audio queueing  │
│                                                                         │
│  user barges in:                                                        │
│  "no the OTHER error" → VAD → stop_speaking()                           │
│                           IMMEDIATELY: POST /api/chat/steer             │
│                           (while Hermes is still running)              │
│                                                      → HERMES           │
│                           Hermes applies steer at next tool boundary    │
│                           New response → buffer → distill → yield → TTS │
│                                                                         │
│  [Hermes] "Ah, you meant the container startup error..."                │
│  [Speaking] "Adjusting — checking container startup..."                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Why LiveKit?

| Feature | LiveKit Provides |
|---------|-----------------|
| WebRTC transport | Encrypted, low-latency audio |
| Real-time transcription | Both user AND agent text published to frontend |
| Barge-in detection | VAD + turn detection built-in |
| Echo cancellation | Agent doesn't hear itself |
| Synthesizer | Accepts `AsyncIterable[str]`, handles sentence boundaries + audio queueing |
| LLM Output Replacement | Intercept text before TTS (distillation point) |

LiveKit's `Synthesizer` accepts `AsyncIterable[str]`. The intermediary is just an adapter:

```python
async def hermes_stream_to_livekit(stream_id: str) -> AsyncIterable[str]:
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

## Three Engines, Not Three Modules

All three behaviors are encoded in the **system prompt** of the intermediary LLM:

| Engine | Mechanism | Latency |
|--------|-----------|---------|
| **Refine** | System prompt: "Clarify messy input before calling tools" | 0ms (implicit in first LLM call) |
| **Distill** | LLM Output Replacement recipe: intercept Hermes text before TTS | <200ms per sentence |
| **Steer** | Barge-in detection → capture text → inject while agent running | <200ms for TTS cut-off |

---

## Platforms

| Platform | Where it lives | What you see |
|----------|---------------|--------------|
| **Browser** | LiveKit room + transcript UI | Full text transcript + voice conversation |
| **Discord** | Voice channel bridge | Text channel transcript + voice conversation |

---

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | ✅ Done | Research, plan, skills loaded |
| 1 | 🔜 Next | LiveKit agent + Hermes API (MVP) |
| 2 | 📋 Planned | TEN Turn Detection (better barge-in) |
| 3 | 📋 Planned | Discord bridge |
| 4 | 📋 Planned | Pipecat concurrent pipeline |

### Phase 1 Sessions

| Session | Focus |
|---------|-------|
| 1 | Core scaffolding + mock Hermes server |
| 2 | Text distillation + logic verification |
| 3 | State-steering engine (barge-in + async sync) |
| 4 | Real Hermes WebUI pipeline integration |
| 5 | Voice + UI layer |
| 6 | Telemetry, verification + video |

---

## Quick Start (Development)

```bash
# Terminal 1: Start LiveKit server
livekit-server --dev

# Terminal 2: Start Hermes WebUI (if not already running)
cd /home/sc/repos/hermes-webui && python3 bootstrap.py

# Terminal 3: Start intermediary agent
cd /home/sc/intermediary-agent && pip install -e .
python3 -m intermediary.agent

# Terminal 4: Start transcript UI
python3 -m webui.app

# Browser: Open http://localhost:8080
```

---

## Documentation

| File | Purpose |
|------|---------|
| `README.md` | This file — overview, architecture, quick start |
| `PLAN.md` | Full implementation plan (DeepThink analysis, component design, data flows, test strategy) |
| `ROADMAP.md` | Phases, milestones, success criteria per phase |
| `INTEGRATION.md` | Hermes API endpoints, LiveKit events, session mapping, config reference |

---

## Architecture Decisions

### Hermes as Separate API (NOT a LiveKit tool)

Hermes is an autonomous multi-agent system with memory, toolsets, and context compression. Forcing it into a single function call strips it of autonomy. Instead:
- LiveKit = sensory interface (ears + mouth)
- Hermes = brain (thinks, uses tools, streams raw text back)

### Steering is User-Initiated (NOT autonomous drift detection)

The intermediary does NOT decide when to intervene. The user does:
- User: "wait, also check auth.log" → captured as steer
- User: "no I meant the OTHER error" → captured as steer

### Steer Timing is Critical

POST `/api/chat/steer` must happen IMMEDIATELY when VAD detects barge-in — NOT after the SSE stream ends. If SSE finishes, the agent run completes and the steer fails with `stream_dead`.

### Distillation Needs a Buffer

SSE deltas are 1-4 characters. You cannot pass sub-word tokens to an LLM for rewriting. The intermediary buffers deltas until sentence boundary, then distills.

---

## External Dependencies

| Dependency | Repo | Purpose |
|---|---|---|
| LiveKit Agents | [livekit/agents](https://github.com/livekit/agents) | Agent framework, WebRTC, plugins |
| Hermes WebUI | [ChonSong/hermes-webui](https://github.com/ChonSong/hermes-webui) | `/api/chat` SSE stream |
| Playwright | [playwright](https://playwright.dev/) | Video evidence for frontend/voice tests |
| Deepgram | [deepgram](https://deepgram.com/) | STT provider |
| Cartesia | [cartesia](https://cartesia.ai/) | TTS provider |
| TEN Framework | [TEN-framework](https://github.com/ten-framework/ten-framework) | Turn detection (Phase 2) |
| Pipecat | [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | Concurrent pipeline (Phase 4) |

---

## License

MIT
