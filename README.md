# Intermediary Agent

> A semantic supervisor that sits between you and an AI agent — refining messy input, distilling verbose output, and steering the agent back on track.

---

## The Problem

| This... | ...is tiring |
|---------|-------------|
| "um so like the docker thing I was talking about earlier? the error?" | → You have to clarify 3 times |
| The agent gives you a 5-paragraph explanation when you wanted the command | → You gave up reading |
| The agent starts explaining Docker history instead of fixing your issue | → You have to interrupt and restart |

## The Solution

An intermediary agent that watches both sides of the conversation:

**1. Refine** your messy spoken/typed input into a clear, actionable prompt

> "um the docker thing?" → "Debug the Docker socket permission error from the previous command"

**2. Distill** the agent's verbose streaming output into natural, concise progress updates

> Agent streaming 3 paragraphs → Intermediary surfaces: "Found 3 issues. Here's the main one:"

**3. Steer** the agent back on track — mid-stream, without stopping the conversation

> Agent goes off-topic → Intermediary injects: "Stay focused. User wants a fix, not an education."

All visible. All editable before sending. No TTS required — this is about meaning, not audio.

---

## How It Works

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  YOU                    INTERMEDIARY                    AGENT    │
│   │                          │                            │      │
│   │  "um the docker thing"   │                            │      │
│   ├─────────────────────────>│                            │      │
│   │                          │  "Debug the Docker socket  │      │
│   │  [you see: raw → refined]│   permission error"       │      │
│   │                          ├───────────────────────────>│      │
│   │                          │                            │      │
│   │                          │  [streaming output]        │      │
│   │                          │  "First, let me check      │      │
│   │                          │   the docs aboutDocker     │      │
│   │                          │   architecture..."         │      │
│   │                          │                            │      │
│   │  "Looking into it..."    │  [distill: progress]       │      │
│   │  "Found 3 issues, here's │                            │      │
│   │   the main one"          │  [detect drift: injecting] │      │
│   │<─────────────────────────┤                            │      │
│   │                          │  "Stay focused on fix"     │      │
│   │                          ├───────────────────────────>│      │
│   │                          │                            │      │
│   │  "Done. Run this:"       │  [corrected response]      │      │
│   │<─────────────────────────┤<───────────────────────────┤      │
│   │                          │                            │      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Architecture

This is a **hermes-agent plugin** that registers pipeline middleware, plus a **WebUI extension** for the browser UI.

```
hermes-agent                      hermes-webui
┌─────────────────────┐          ┌─────────────────────┐
│  Discord adapter    │          │  Two-pane composer  │
│  Webhook adapter    │          │  Intermediary pane  │
│       │             │          │       │             │
│  ┌────┴──────────┐  │          │  ┌────┴──────────┐  │
│  │  Intermediary  │  │◄═════════►│  WebUI ext     │  │
│  │  Plugin        │  │   SSE     │                │  │
│  └────┬──────────┘  │           └────────────────┘  │
│       │             │                                │
│  ┌────┴──────────┐  │                                │
│  │  Refine       │  │                                │
│  │  Distill      │  │                                │
│  │  Steer        │  │                                │
│  └───────────────┘  │                                │
└─────────────────────┘
```

### Three Engines

| Engine | Input | Output | Latency |
|--------|-------|--------|---------|
| **Refine** | Raw user text + conversation context | Structured, actionable prompt | < 500ms |
| **Distill** | Streaming agent tokens + user intent | Natural progress updates (1-2s cadence) | Concurrent |
| **Steer** | Streaming output + intent baseline | null (aligned) \| correction injection | < 1s |

### Steering: Uses Existing `agent.steer()`

The intermediary does NOT reinvent steering. Hermes already has `agent.steer(text)` which injects into the next tool result without interrupting. The intermediary hooks into this:

```python
# Detect drift → inject correction (non-interrupting)
agent.steer("Stay focused on fixing the bug")
# → Next tool result gets "User guidance: Stay focused on fixing the bug"
# → Agent adjusts course without interruption
```

### Audio Sublayer: Pluggable from Day One

| Backend | What it does | When to use |
|---------|-------------|-------------|
| **TEN Turn Detection** | Yield-floor detection (open-source) | Knowing *when* to speak |
| **Pipecat Pipeline** | Concurrent STT+LLM+TTS | True full-duplex |
| **LiveKit Transport** | WebRTC for browser voice | WebUI voice |

Swap via config: `audio.backend: ten` → `audio.backend: pipecat`, no code changes.

---

## Platforms

| Platform | Where it lives | What you see |
|----------|---------------|--------------|
| **WebUI** | Two-pane composer + sidebar | Raw + refined text; progress updates during agent response |
| **Discord** | Text channel messages (edit pattern) | Transcribed → refined → progress → final, all in text |
| **CLI/TUI** | Status line + transcript | Quick progress indicators, refined text before send |

---

## Why Not Pipecat / LiveKit / TEN?

| Framework | What it does | Why we don't need it |
|-----------|--------------|---------------------|
| **Pipecat** | Voice IO pipeline (STT → LLM → TTS) | We don't do audio output; intermediary refines text |
| **LiveKit** | WebRTC transport + voice agents | Transport layer; assumes agent output is audio |
| **TEN Framework** | Full-duplex voice, turn detection | Audio-focused; we're meaning-focused |
| **Vapi / Retell** | Voice agent SaaS for telephony | Closed-source, phone-focused |

All of these frameworks assume the **output is audio**. We're building a **semantic supervisor** that manages *meaning*. None of them have a concept of "refining input" or "distilling output" — they just pipe audio through.

We might borrow **TEN Turn Detection** later (it's open-source) for knowing when to intervene, but the rest is in-house.

---

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | 🔜 Starting | Hermes-agent plugin (text, Discord) |
| 2 | 📋 Planned | Voice input (Discord) |
| 3 | 📋 Planned | Steering engine |
| 4 | 📋 Planned | WebUI extension |
| 5 | 📋 Planned | CLI/TUI surface |
| 6 | 📋 Planned | Hardening |

### Phase 1 Success Criteria (human-verifiable)

These are tests a human can run — no automated test suite needed to start:

- [ ] **Refine works**: User types "um the docker thing?" → intermediary shows refined "Debug the Docker permission error" before agent sees it
- [ ] **Edit pattern works**: Progress message in Discord is edited (not new messages), max ~3 updates visible at once
- [ ] **Latency**: Refined text appears < 1 second after user hits Enter
- [ ] **Distill works**: Agent's 3-paragraph response → intermediary shows 3 short progress updates then a final summary
- [ ] **No spam**: Between question and answer, intermediary shows ≤ 5 updates total
- [ ] **Graceful fallback**: If intermediary is offline, conversation still works normally (pass-through)

See [ROADMAP.md](ROADMAP.md) for all phases' success criteria.

---

## Integration Points

**hermes-agent** (pipeline hooks):
| File | Change |
|------|--------|
| `hermes_cli/plugins.py` | Add `intermediary_*` hooks to `VALID_HOOKS` |
| `gateway/platforms/discord.py` | Wire intermediary surface (minimal) |
| `hermes_cli/config.py` | Add `intermediary:` config section |

**hermes-webui** (extension):
| File | Change |
|------|--------|
| `static/boot.js` | Intercept STT/text input, send to intermediary |
| `static/ui.js` | Two-pane composer, progress sidebar |
| `api/extensions.py` | SSE endpoint for intermediary events |

Full integration reference: [INTEGRATION.md](INTEGRATION.md)

---

## Repo Structure

```
intermediary-agent/
  README.md              # You are here
  PLAN.md                # Full architecture, component design, prompts
  ROADMAP.md             # Phases, milestones, success criteria
  INTEGRATION.md         # File paths, function signatures, code examples
  intermediary/
    __init__.py          # Plugin entry (register hooks)
    plugin.yaml          # Plugin manifest
    config.py            # Config schema + defaults
    state.py             # Per-session state (intent, context)
    refine.py            # Input refinement engine
    distill.py           # Output distillation engine
    steer.py             # Drift detection + correction
    hooks.py             # Hook registration
  surfaces/
    discord_surface.py   # Discord renderer
    webui_surface.py     # WebUI SSE bridge
    cli_surface.py       # CLI status line
  prompts/
    refine_system.md     # "Restructure messy input..."
    distill_system.md    # "Produce natural progress update..."
    steer_system.md      # "Detect drift, inject correction..."
  webui_extension/
    intermediary.css     # Styles
    intermediary.js      # Client-side logic
    manifest.json        # Extension manifest
  tests/
    test_refine.py       # Unit + mock LLM tests
    test_distill.py      # Unit + mock streaming tests
    test_steer.py        # Drift detection tests
    test_hooks.py        # Integration tests with hermes-agent mock
```

---

## Using This Repo

### Development

```bash
# Clone
git clone https://github.com/ChonSong/intermediary-agent.git
cd intermediary-agent

# Install in hermes-agent plugin directory
pip install -e hermes-agent  # links to ~/.hermes/plugins/intermediary

# Enable in config
# Add to ~/.hermes/config.yaml:
#   plugins:
#     enabled:
#       - intermediary

# Run with hermes-agent
hermes gateway
```

### Documentation

- New contributor? Start with [PLAN.md](PLAN.md) for the full architecture
- Want to extend? Check [INTEGRATION.md](INTEGRATION.md) for exact code paths
- Tracking progress? See [ROADMAP.md](ROADMAP.md) for phases and milestones

---

## License

MIT
