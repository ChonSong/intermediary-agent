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

> You barge in: "no the OTHER error" → Intermediary captures → injects after Hermes finishes: "[User guidance] no the OTHER error"

**4. Watch everything** — full text transcript in the browser while you converse by voice

## How It Works

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER                                      │
│                                                                  │
│  ┌─────────────┐    LiveKit WebRTC     ┌──────────────────┐     │
│  │  Speaks     │ ←──────────────────→  │  Listens         │     │
│  │  Sees text  │    (voice stream)      │  Hears voice     │     │
│  │  transcript │                       │                  │     │
│  └─────────────┘                       └──────────────────┘     │
│         │                                        │               │
│         │         ┌─────────────────────┐        │               │
│         │         │  LIVEKIT AGENT      │        │               │
│         │         │  (Intermediary)     │        │               │
│         │         │                     │        │               │
│    STT  │         │  ┌───────────────┐  │  TTS   │               │
│   ─────→│────────→│  │ Intermediary  │  │ ──────→│               │
│         │         │  │ LLM           │  │        │               │
│         │         │  │ (lightweight) │  │        │               │
│         │         │  └───────┬───────┘  │        │               │
│         │         │          │          │        │               │
│         │         │     HTTP POST (SSE)  │        │               │
│         │         │          │          │        │               │
│         │         └──────────┼──────────┘        │               │
│         │                    │                    │               │
│         │                    ↓                    │               │
│         │         ┌─────────────────────┐        │               │
│         │         │  HERMES WEBUI API   │        │               │
│         │         │  (separate instance)│        │               │
│         │         │                     │        │               │
│         │         │  • Full reasoning   │        │               │
│         │         │  • Tools            │        │               │
│         │         │  • Memory           │        │               │
│         │         │  • Context          │        │               │
│         │         └─────────────────────┘        │               │
│         │                                        │               │
│         ↓                                        │               │
│  ┌─────────────────────────────────────────┐     │               │
│  │  TRANSCRIPT UI                          │     │               │
│  │                                         │     │               │
│  │  [You] "um the docker thing?"           │     │               │
│  │  [Intermediary] → "Debug the Docker     │     │               │
│  │                permission error"        │     │               │
│  │  [Hermes] "First, let me check..."      │     │               │
│  │  [Speaking] "Checking the logs..."      │     │               │
│  │  [You] "[Steer] no the OTHER error"     │     │               │
│  │  [Hermes] "Ah, you meant the..."        │     │               │
│  └─────────────────────────────────────────┘     │               │
└──────────────────────────────────────────────────────────────────┘
```

---

## Why LiveKit?

| Feature | LiveKit Provides |
|---------|-----------------|
| WebRTC transport | Encrypted, low-latency audio |
| Real-time transcription | Both user AND agent text published to frontend |
| Barge-in detection | VAD + turn detection built-in |
| Echo cancellation | Agent doesn't hear itself |
| Plugin ecosystem | Deepgram STT, Cartesia TTS, OpenAI LLM |
| LLM Output Replacement | Intercept text before TTS (distillation point) |

LiveKit gives us the "watch everything" text visibility AND the "converse by voice" interaction from day one.

---

## Three Engines, One Prompt

The intermediary does NOT use separate Python modules for refine/distill/steer. All three are encoded in the **system prompt** of a single lightweight LLM:

| Engine | Mechanism | Latency |
|--------|-----------|---------|
| **Refine** | System prompt: "Clarify messy input before calling tools" | 0ms (implicit in first LLM call) |
| **Distill** | LLM Output Replacement recipe: intercept Hermes text before TTS | <200ms per chunk |
| **Steer** | Barge-in detection → capture text → inject after Hermes finishes | <200ms for TTS cut-off |

---

## Platforms

| Platform | Where it lives | What you see |
|----------|---------------|--------------|
| **Browser** | LiveKit room + transcript UI | Full text transcript + voice conversation |
| **Discord** | Voice channel bridge | Text channel transcript + voice conversation |
| **CLI** | Terminal (future) | Status line + refined display |

---

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | ✅ Done | Research, plan, skills loaded |
| 1 | 🔜 Next | LiveKit agent + Hermes API (MVP) |
| 2 | 📋 Planned | TEN Turn Detection (full-duplex) |
| 3 | 📋 Planned | Discord bridge |
| 4 | 📋 Planned | Pipecat concurrent pipeline |
| 5 | 📋 Planned | WebUI extension |
| 6 | 📋 Planned | Hardening |

### Phase 1 Success Criteria (human-verifiable)

- [ ] User speaks → STT → refined text sent to Hermes
- [ ] Hermes response → distilled → TTS speaks
- [ ] User sees full text transcript in browser
- [ ] User barge-in → TTS stops → steer injected
- [ ] Video evidence in `test-evidence/videos/phase1-e2e.webm`

---

## Quick Start (Development)

```bash
# Terminal 1: Start LiveKit server
livekit-server --dev

# Terminal 2: Start Hermes WebUI
cd /home/sc/repos/hermes-webui && python3 bootstrap.py

# Terminal 3: Start intermediary agent
cd /home/sc/intermediary-agent && pip install -e .
python3 -m intermediary.agent

# Terminal 4: Start frontend
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
- Intermediary just routes the steer to Hermes via `[User guidance]` prefix

### Zero Changes to Hermes (Phase 1)

Phase 1 uses the existing Hermes WebUI API (`/api/chat`, `/api/sessions`). No modifications to hermes-agent or hermes-webui required.

---

## External Dependencies

| Dependency | Repo | Purpose |
|---|---|---|
| LiveKit Agents | [livekit/agents](https://github.com/livekit/agents) | Agent framework, WebRTC, plugins |
| Hermes WebUI | [ChonSong/hermes-webui](https://github.com/ChonSong/hermes-webui) | `/api/chat` SSE stream |
| TEN Framework | [TEN-framework](https://github.com/ten-framework/ten-framework) | Full-duplex turn detection |
| Pipecat | [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | Concurrent STT+LLM+TTS |
| Playwright | [playwright](https://playwright.dev/) | Video evidence for tests |

---

## License

MIT
