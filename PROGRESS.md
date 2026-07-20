# Intermediary Agent — Progress Tracking

| Phase | Status | What was done | What's next |
|-------|--------|---------------|-------------|
| 0 | ✅ Done | README, PLAN, ROADMAP, INTEGRATION docs | — |
| Spike 03 | ✅ Done | Pure-logic spike, found + fixed 2 bugs | — |
| 1.1 | ✅ Done | Scaffold, HermesClient, mock server, 5 tests | — |
| 1.4 | ✅ Done | Distillation buffer + 28 unit tests | — |
| 1.6a | ✅ Done | Barge-in state machine + 10 integration tests | — |
| 1.5 | ✅ Done | Text MVP — TextIntermediary, FastAPI SSE, frontend | — |
| 1.6b | ✅ Done | Real Hermes API wired (cookie auth, session, streaming) | — |
| 1.7 | ✅ Done | Reasoning filter — only final answer shown | — |
| 2 | ✅ Done | WebUI extension — panel scaffolding | Connect in WebUI, test |
| 3 | 📋 Planned | Voice pipeline (Local models, no LiveKit) | — |
| 4 | 📋 Planned | Discord bridge | — |

**MVP Status:** 
- Text MVP working with REAL Hermes (port 8080)
- Refinement, streaming, real answer extraction
- WebUI extension scaffolded
- 64 tests passing

Run with:
```bash
cd /home/sc/intermediary-agent
HERMES_MOCK=false python -m uvicorn webui.text_server:app --host 0.0.0.0 --port 8080
```

Last update: 2026-07-20
