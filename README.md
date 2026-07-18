# Intermediary Agent

> A semantic supervisor that sits between you and Hermes — refining messy input, distilling verbose output, and steering the agent back on track.

## The Problem

You speak in fragments. Hermes responds in essays. The back-and-forth is slow, and the agent drifts off-topic.

## The Solution

An intermediary agent that:

1. **Refines** your messy spoken/typed input into structured, actionable prompts
2. **Distills** Hermes' verbose streaming output into natural, concise progress updates
3. **Steers** Hermes mid-stream when it goes off-topic — injecting corrections without stopping the conversation

All visible. All editable. No TTS required.

## How It Works

```
You → [STT] → Raw transcript → ┌─────────────────────────────┐
                                │  INTERMEDIARY               │
                                │  • Refine: "um the docker    │
                                │    thing?" → "Debug the      │
                                │    Docker permission error"  │
                                │  • Surface: "Looking into    │
                                │    it..."                    │
                                └─────────────────────────────┘
                                          ↓
                                Hermes processes refined prompt
                                          ↓
                                Streaming output → ┌─────────────────────────┐
                                                  │  • Distill: "Found 3    │
                                                  │    issues, here's the   │
                                                  │    main one"            │
                                                  │  • Steer: "Stay focused │
                                                  │    on fix, not explain" │
                                                  └─────────────────────────┘
```

## Platforms

| Platform | Input | Intermediary Output | Hermes Output |
|----------|-------|---------------------|---------------|
| **WebUI** | Mic / text | Two-pane composer (raw + refined) + sidebar progress | Chat panel |
| **Discord** | Voice / text | Text channel updates (edit-message pattern) | Text channel |
| **CLI/TUI** | Mic / text | Status line updates | Terminal |

## Architecture

This is a **hermes-agent plugin** that registers pipeline middleware hooks:

- `pre_gateway_dispatch` — intercept incoming messages, refine them
- `pre_llm_call` — inject steering messages when needed
- `post_llm_call` — distill the response, surface progress
- `inject_message()` — inject corrections mid-turn

Plus a **WebUI extension** that renders the intermediary pane and handles the two-pane composer.

## Status

🚧 Active development. See [ROADMAP.md](ROADMAP.md) for the plan.

## License

MIT
