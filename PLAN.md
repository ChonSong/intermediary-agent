# Intermediary Agent — Complete Implementation Plan

> LiveKit-based intermediary that sits between user and Hermes. Thin voice interface, full text visibility, non-interrupting steer.

---

## Table of Contents

1. [DeepThink Analysis](#deepthink-analysis)
2. [Architecture Overview](#architecture-overview)
3. [File Structure](#file-structure)
4. [Component Design](#component-design)
5. [Hermes API Integration](#hermes-api-integration)
6. [LiveKit Integration](#livekit-integration)
7. [Data Flow](#data-flow)
8. [Barge-in State Machine](#barge-in-state-machine)
9. [Session Mapping](#session-mapping)
10. [Prompt Engineering](#prompt-engineering)
11. [Frontend (Transcript UI)](#frontend-transcript-ui)
12. [Test Strategy](#test-strategy)
13. [Integration Points](#integration-points)
14. [Performance Requirements](#performance-requirements)
15. [Security & Privacy](#security--privacy)

---

## DeepThink Analysis

### Loop 1 — Surface

**Problem**: Design a voice intermediary that lets the user converse with Hermes by voice while watching the full text exchange.

**Initial hypothesis**: Use LiveKit's `VoicePipelineAgent` (high-level class) which chains STT→LLT→TTS automatically. The LLM in the middle is the intermediary. Hermes is called as a function/tool from within the LiveKit agent.

### Loop 2 — Explore

**LiveKit research findings:**

- `VoicePipelineAgent` is turn-based: LLM turn doesn't end until TTS is done. This makes barge-in awkward.
- `Agent` + `AgentSession` (lower-level API) supports frame-level streaming — can push chunks to TTS while listening for user speech simultaneously.
- LiveKit publishes `TranscriptionReceived` events for both user AND agent speech. Frontend subscribes via `room.on(RoomEvent.TranscriptionReceived, ...)`.
- `LLM Output Replacement` recipe — intercept LLM text before it hits TTS. This is where distillation happens.
- LiveKit's `FunctionCalling` support — agent can call tools OR forward to external API.

**Hermes research findings:**

- WebUI exposes `POST /api/chat` with SSE streaming (`text/event-stream` with `delta` chunks).
- WebUI `POST /api/sessions` creates sessions.
- Gateway exposes `:8642` if `API_SERVER_ENABLED=true`.
- Existing `/steer` mechanism: `agent.steer(text)` injects into next tool result WITHOUT interruption.
- Existing `inject_message()` — INTERRUPTS the agent (different!).

**Decision**: Hermes as separate API (option B). NOT a LiveKit tool.

**Why not (A)**:
- Hermes is an autonomous multi-agent system with memory, toolsets, context compression, sub-agent orchestration.
- Forcing it into a single function call strips Hermes of its autonomy.
- The intermediary LLM would have to manage Hermes's reasoning, which is architecturally wrong.

**Why (B)**:
- LiveKit acts as sensory interface (ears + mouth).
- Hermes thinks, uses its own tools, streams raw text back to intermediary for distillation.
- Decoupled: telemetry, debugging, and monitoring are clean.

### Loop 3 — Challenge

**What could go wrong?**

| Risk | Severity | Mitigation |
|------|----------|------------|
| Hermes runs a 30-second tool — user hears silence | High | Intermediary says "Working on it..." while waiting for first chunk |
| Refinement adds latency | Medium | Make refinement part of system prompt (single LLM call), not separate |
| Distillation quality vs latency tradeoff | Medium | Use fast model (GPT-4o-mini, Gemini Flash) for intermediary; big model for Hermes |
| Barge-in race condition: Hermes still streaming after user interrupts | High | Track `generation_id` per exchange; increment on barge-in; discard stale chunks |
| Session state: LiveKit session ≠ Hermes session | Medium | One-to-one mapping: LiveKit participant → Hermes session_id |
| TTS playback triggers own STT (echo) | Medium | LiveKit has built-in echo cancellation; also mute mic during TTS |
| Refinement "over-corrects" and changes user intent | High | System prompt: "Preserve intent exactly. Only clarify vagueness, never replace." |

**Critical decision: How to handle Hermes calling.**

The intermediary could:
1. Call Hermes via LiveKit function calling (agent tool)
2. Call Hermes via direct HTTP in event handler (no function calling)

Option 2 is simpler and more flexible. The intermediary's event handler calls `hermes_client.send_message()` directly. No need for LiveKit's function calling machinery.

**Decision: Option 2**. Direct HTTP call from event handler.

### Loop 4 — Synthesize

**Final architecture**:

```
User ←→ (LiveKit WebRTC) ←→ Intermediary Agent ←→ (HTTP/SSE) ←→ Hermes
  ↕                                                                       ↕
 Sees text transcript                                              Does reasoning
 Hears distilled voice                                              Runs tools
 Can barge-in / steer                                               Returns raw text
```

**Refinement**: Built into system prompt. Intermediary LLM sees user text + conversation context. Its first action is to call `hermes_client.send_message()` with the clarified prompt.

**Distillation**: Use LiveKit's `LLM Output Replacement` recipe. Raw Hermes response chunks go through a fast summarizer before being pushed to TTS.

**Steering**: User barges in → `stop_speaking()` → capture text → store as `pending_steer`. When Hermes finishes current step, inject steer as next message prefixed with `[User guidance]`.

**Visibility**: Forward `TranscriptionReceived` events to browser via WebSocket. Frontend renders a live transcript panel.

### Loop 5 — Converge

Architecture is stable. Key principles:
- Intermediary is thin — no heavy reasoning, just clarity + distillation + routing
- Hermes stays autonomous — full tool/memory/compression capabilities preserved
- Text is the visibility layer, voice is the interaction layer
- LiveKit handles WebRTC, echo cancellation, turn detection
- Direct HTTP calls to Hermes API (not LiveKit function calling)

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                              USER                                      │
│                                                                        │
│  ┌────────────────┐    LiveKit WebRTC     ┌────────────────────┐      │
│  │  Microphone    │ ←──────────────────→  │  Speakers          │      │
│  │  Browser UI    │    ( audio stream )    │  (hear voice)      │      │
│  │  Transcript    │                        │                    │      │
│  └────────────────┘                        └────────────────────┘      │
│         │                                            │                 │
│         │         ┌──────────────────────────┐       │                 │
│         │         │    LIVEKIT ROOM          │       │                 │
│         │         │    (Intermediary Agent)  │       │                 │
│         │         │                          │       │                 │
│    STT  │         │  ┌────────────────────┐  │  TTS  │                 │
│   ─────→│────────→│  │ Intermediary LLM   │  │←──────│                 │
│         │         │  │ (lightweight)      │  │       │                 │
│         │         │  │                    │  │       │                 │
│         │         │  │ • Refine (prompt)  │  │       │                 │
│         │         │  │ • Distill (filter) │  │       │                 │
│         │         │  │ • Steer (barge-in) │  │       │                 │
│         │         │  └─────────┬──────────┘  │       │                 │
│         │         │            │             │       │                 │
│         │         │     HTTP POST (SSE)      │       │                 │
│         │         │            │             │       │                 │
│         │         └────────────┼─────────────┘       │                 │
│         │                      │                     │                 │
│         │                      ↓                     │                 │
│         │         ┌──────────────────────────┐       │                 │
│         │         │    HERMES API            │       │                 │
│         │         │    (separate instance)   │       │                 │
│         │         │                          │       │                 │
│         │         │  • Full reasoning        │       │                 │
│         │         │  • Tools                 │       │                 │
│         │         │  • Memory                │       │                 │
│         │         │  • Context compression   │       │                 │
│         │         │  • Sub-agent编排         │       │                 │
│         │         └──────────────────────────┘       │                 │
│         │                                            │                 │
│         ↓                                            │                 │
│  ┌─────────────────────────────────────────────┐     │                 │
│  │  FRONTEND TRANSCRIPT UI                     │     │                 │
│  │                                             │     │                 │
│  │  [You] (raw): "um the docker thing?"        │     │                 │
│  │  [Intermediary]: "Refining: Debug the       │     │                 │
│  │                Docker permission error"      │     │                 │
│  │  [Hermes] (raw): "First, let me check..."   │     │                 │
│  │  [Intermediary] (spoken): "Checking logs"   │     │                 │
│  │  ...                                        │     │                 │
│  └─────────────────────────────────────────────┘     │                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
intermediary-agent/
├── README.md                       # Project overview, quick start
├── PLAN.md                         # This file — full implementation plan
├── ROADMAP.md                      # Phases, milestones, success criteria
├── INTEGRATION.md                  # External repo file paths + changes
├── pyproject.toml                  # Python package config
├── intermediary/
│   ├── __init__.py
│   ├── agent.py                    # LiveKit Agent subclass — the intermediary
│   ├── hermes_client.py            # HTTP client for Hermes API (SSE streaming)
│   ├── refinement.py               # Refinement logic (system prompt based)
│   ├── distillation.py             # LLM Output Replacement for Hermes responses
│   ├── steering.py                 # Barge-in capture + steer injection
│   ├── session.py                  # Session state management
│   ├── prompts.py                  # System prompt templates
│   └── audio_config.py             # Audio backend configuration
├── audio/
│   ├── __init__.py
│   ├── base.py                     # AudioBackend ABC
│   ├── livekit_native.py           # LiveKit built-in STT/TTS (default)
│   ├── ten_backend.py              # TEN Turn Detection (full-duplex)
│   ├── pipecat_backend.py          # Pipecat concurrent pipeline
│   └── discord_bridge.py           # Discord VoiceReceiver bridge
├── webui/
│   ├── __init__.py
│   ├── app.py                      # FastAPI app serving transcript UI
│   ├── static/
│   │   ├── transcript.js           # LiveKit transcription display
│   │   └── styles.css              # Transcript UI styling
│   └── templates/
│       └── index.html              # Transcript UI template
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Playwright config (video recording)
│   ├── test_refinement.py          # Refinement unit tests
│   ├── test_distillation.py        # Distillation unit tests
│   ├── test_steering.py            # Barge-in + steer tests
│   ├── test_hermes_client.py       # Hermes API client tests
│   ├── test_agent.py               # LiveKit agent integration test
│   ├── test_transcript_ui.py       # Frontend transcript display test
│   └── test_e2e.py                 # Full E2E test with real Hermes
├── test-evidence/
│   ├── videos/                     # Playwright video recordings
│   └── screenshots/                # Playwright screenshots
└── scripts/
    ├── dev.sh                      # Run locally with LiveKit CLI
    └── doctor.sh                   # Self-diagnostic
```

---

## Component Design

### 1. Intermediary Agent (`intermediary/agent.py`)

```python
from livekit.agents import Agent, AgentSession
from livekit.agents.llm import ChatContext

class IntermediaryAgent(Agent):
    """
    LiveKit Agent subclass — the intermediary between user and Hermes.
    
    Responsibilities:
    - Receive user speech via STT events
    - Clarify/refine messy input (via system prompt)
    - Forward refined text to Hermes API via HTTP
    - Receive Hermes response stream
    - Distill each chunk for natural speech
    - Push distilled text to TTS
    - Handle barge-in (user interrupts while agent is speaking)
    - Forward transcription events to frontend WebSocket
    """
    
    def __init__(
        self,
        hermes_url: str,
        intermediary_model: str = "openai/gpt-4o-mini",
        instructions: str = None,
    ):
        super().__init__(
            instructions=instructions or INTERMEDIARY_SYSTEM_PROMPT,
        )
        self.hermes_url = hermes_url
        self.hermes_client = HermesClient(hermes_url)
        self.session_state: dict[str, SessionState] = {}
        self.pending_steer: dict[str, str] = {}  # room -> pending steer
        self.current_generation: dict[str, int] = {}  # room -> generation counter
    
    async def on_enter(self):
        """Called when agent joins the room."""
        # Get room name / participant info
        # Create mapping: room -> Hermes session
    
    async def on_user_speech_committed(
        self, session: AgentSession, text: str
    ):
        """
        Called when STT commits user speech.
        
        If user is currently speaking while agent is talking → barge-in.
        Otherwise → normal turn.
        """
        room = session.room.name
        
        if self._is_barge_in(session):
            # User interrupted the agent
            await self._handle_barge_in(session, text)
        else:
            # Normal turn
            await self._handle_user_turn(session, text)
    
    async def _handle_user_turn(
        self, session: AgentSession, text: str
    ):
        """
        Normal user turn: refine → send to Hermes → distill response → speak.
        """
        room = session.room.name
        
        # 1. Refine (via system prompt — single LLM call)
        #    The intermediary LLM sees user text + context
        #    and generates a refined Hermes query
        
        # 2. Send to Hermes
        async for chunk in self.hermes_client.send_message(
            message=text,
            session_id=self.session_state[room].hermes_session_id,
        ):
            # 3. Distill each chunk
            distilled = await self.distill(chunk)
            
            # 4. Speak
            session.say(distilled)
            
            # 5. Forward to transcript UI
            self._forward_transcription(room, chunk, "hermes")
        
        # 6. After Hermes finishes, check for pending steer
        if room in self.pending_steer:
            steer_text = self.pending_steer.pop(room)
            await self._handle_user_turn(
                session, f"[User guidance] {steer_text}"
            )
    
    async def _handle_barge_in(
        self, session: AgentSession, text: str
    ):
        """
        User interrupted the agent mid-speech.
        
        - Stop speaking immediately
        - Capture user text as pending steer
        - Do NOT restart immediately (let Hermes finish current step)
        """
        room = session.room.name
        
        # Stop TTS
        session.stop_speaking()
        
        # Capture steer
        self.pending_steer[room] = text
        self.current_generation[room] += 1
        
        # Forward to transcript UI
        self._forward_transcription(
            room, f"[Steer] {text}", "user"
        )
    
    def _is_barge_in(self, session: AgentSession) -> bool:
        """Check if user is speaking while agent is currently talking."""
        return session.currently_speaking
    
    async def distill(self, raw_chunk: str) -> str:
        """
        Distill a raw Hermes response chunk for natural speech.
        
        Uses LLM Output Replacement pattern:
        - Strip chain-of-thought / thinking blocks
        - Summarize technical output to 1-2 sentences
        - Keep natural conversational tone
        """
        # Fast summarization
        ...
    
    def _forward_transcription(
        self, room: str, text: str, speaker: str
    ):
        """Forward transcription event to frontend via WebSocket."""
        ...
```

### 2. Hermes API Client (`intermediary/hermes_client.py`)

```python
import aiohttp
import json
from typing import AsyncIterator

class HermesClient:
    """
    HTTP client for Hermes WebUI API.
    
    Uses SSE streaming to receive response chunks as they are generated.
    """
    
    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
    
    async def create_session(self) -> str:
        """Create a new Hermes session. Return session_id."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/sessions",
                headers=self._auth_headers(),
            ) as resp:
                data = await resp.json()
                return data["session_id"]
    
    async def send_message(
        self,
        message: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """
        Send a message to Hermes, yield response text chunks.
        
        Handles:
        - SSE stream parsing (data: {...}\n\n format)
        - Delta chunks (type=delta, content=text)
        - Tool use chunks
        - Error chunks
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/chat",
                json={
                    "message": message,
                    "session_id": session_id,
                },
                headers=self._auth_headers(),
            ) as resp:
                async for line in resp.content:
                    if not line.startswith(b"data: "):
                        continue
                    try:
                        data = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    
                    match data.get("type"):
                        case "delta":
                            yield data["content"]
                        case "tool_use":
                            # Optionally emit tool-visible chunks
                            pass
                        case "error":
                            yield f"[Error: {data.get('message', 'unknown')}]"
                        case "done":
                            return
    
    def _auth_headers(self) -> dict:
        """Build auth headers for Hermes API."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
```

### 3. Refinement Logic (`intermediary/refinement.py`)

Refinement is built into the system prompt. The intermediary LLM sees user text + conversation context. Its first action is to call hermes client with the clarified prompt.

**Option A (chosen)**: System prompt includes refinement instructions. The intermediary LLM does refinement implicitly as part of generating the Hermes query.

**Option B (rejected)**: Separate refinement LLM call. Adds latency.

**System prompt snippet:**
```
REFINEMENT RULES:
- Resolve pronouns ("that thing", "the error") using conversation history
- Expand vague references to specific terms
- Structure as: [Action] + [Context] + [Constraints]
- Output ONLY the refined query. Never add interpretation.

CONVERSATION CONTEXT:
- Previous topics: {intent_history}
- Current focus: {current_topic}
```

### 4. Distillation Logic (`intermediary/distillation.py`)

Distillation uses LiveKit's `LLM Output Replacement` recipe.

```python
from livekit.agents import llm

class DistillationFilter(llm.Modification():
    """
    LiveKit LLM Output Replacement recipe.
    
    Intercepts raw Hermes response text before it reaches TTS.
    Summarizes technical output for natural speech.
    """
    
    def __init__(self, model: str = "openai/gpt-4o-mini"):
        self.model = model
    
    async def modify(
        self, text: str, context: llm.ChatContext
    ) -> str:
        """
        Transform raw Hermes response chunk into natural speech.
        
        Rules:
        - Strip chain-of-thought / thinking blocks
        - Summarize to 1-2 sentences
        - Conversational tone
        - If nothing useful: return '' (suppress)
        """
        # Fast LLM call to summarize
        ...
```

**Prompt for distillation (if using LLM):**
```
Summarize the following AI agent response for natural speech.
Output 1-2 sentences, conversational tone, nothing else.

Response: {raw_chunk}
Summary:
```

**Heuristic distillation (if not using LLM):**
- Strip text between `<think>` and `</think>` tags
- Take first 1-2 sentences
- Skip markdown formatting
- Skip tool-use JSON

### 5. Steering Logic (`intermediary/steering.py`)

```python
class SteeringController:
    """
    Manages barge-in capture and steer injection.
    
    Lifecycle:
    1. User is speaking while agent is talking (barge-in detected)
    2. Agent stops speaking
    3. User text is stored as pending steer
    4. Agent finishes current Hermes response
    5. Pending steer is injected as next user message
    """
    
    def __init__(self):
        self.pending_steer: dict[str, str] = {}  # room -> steer text
        self.steer_history: dict[str, list[str]] = {}  # room -> past steers
    
    def capture_steer(self, room: str, text: str):
        """Called when user barges in."""
        self.pending_steer[room] = text
        self.steer_history.setdefault(room, []).append(text)
    
    def get_pending_steer(self, room: str) -> str | None:
        """Get and clear pending steer."""
        return self.pending_steer.pop(room, None)
    
    def has_pending_steer(self, room: str) -> bool:
        return room in self.pending_steer
    
    def format_steer_for_hermes(self, text: str) -> str:
        """Format steer text as a Hermes message."""
        return f"[User guidance] {text}"
```

### 6. Session State (`intermediary/session.py`)

```python
from dataclasses import dataclass, field

@dataclass
class SessionState:
    """
    Per-participant session state.
    Maps LiveKit participant → Hermes session.
    """
    room: str
    participant_identity: str
    hermes_session_id: str
    hermes_url: str
    intent_history: list[str] = field(default_factory=list)
    current_topic: str = ""
    current_generation: int = 0
    
    def update_intent(self, new_intent: str):
        """Add new intent to history, update current topic."""
        self.intent_history.append(new_intent)
        self.current_topic = new_intent
        # Keep only last 10 for context window
        self.intent_history = self.intent_history[-10:]
    
    def next_generation(self) -> int:
        """Increment generation counter (for barge-in invalidation)."""
        self.current_generation += 1
        return self.current_generation
```

### 7. Prompts (`intermediary/prompts.py`)

```python
INTERMEDIARY_SYSTEM_PROMPT = """\
You are a **thin intermediary** between the user and Hermes (a powerful AI agent).

## Your Role

You are NOT a heavy reasoner. You are the user's ears and mouth:
- Clarify messy input BEFORE sending to Hermes
- Distill verbose output for natural speech
- Handle interruptions gracefully

## Refinement Rules

When the user speaks in fragments or with vague references:
1. Resolve pronouns using conversation history ("that thing", "the error")
2. Expand vague references to specific terms
3. Structure as: [Action] + [Context] + [Constraints]
4. Output ONLY the refined query. Never add interpretation.
5. If no refinement needed, pass through unchanged.

## Distillation Rules

When Hermes responds with long technical output:
1. Summarize to 1-2 sentences for natural speech
2. Strip chain-of-thought / thinking blocks
3. Strip markdown formatting
4. Conversational tone like a colleague updating you
5. If nothing useful: suppress (don't speak)

## Steering Rules

When the user interrupts (barge-in):
1. Stop speaking immediately
2. Capture their correction
3. After Hermes finishes current step, inject steer as: "[User guidance] <text>"
4. Do NOT restart immediately — let Hermes finish its current reasoning

## Context

Previous topics: {intent_history}
Current focus: {current_topic}
"""
```

---

## Hermes API Integration

### Endpoints Used

| Endpoint | Method | Purpose | When |
|----------|--------|---------|------|
| `/api/sessions` | POST | Create new Hermes session | On LiveKit participant connect |
| `/api/sessions` | GET | List active sessions | Diagnostic |
| `/api/chat` | POST | Send message, receive SSE stream | Every user turn |
| `/api/chat` | POST | Inject steer | After barge-in |
| `/api/settings` | GET | Get session settings | Optional |

### SSE Stream Format

```
data: {"type": "delta", "content": "First, let me check"}

data: {"type": "delta", "content": " the logs."}

data: {"type": "tool_use", "tool": "read_file", "args": {"path": "/var/log/syslog"}}

data: {"type": "delta", "content": "Found the issue!"}

data: {"type": "done"}
```

### Hermes Response Types

| Type | What to do |
|------|-----------|
| `delta` | Pass to distillation → TTS → transcript UI |
| `tool_use` | Optionally show "Using tool: X" in transcript |
| `thinking` / `CoT` | Suppress from TTS, optionally show in transcript |
| `error` | Speak error message, show in transcript |
| `done` | Check for pending steer, cleanup |

### Session Mapping

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

---

## LiveKit Integration

### LiveKit Agent Lifecycle

```
1. Room created
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

---

## Data Flow

### Normal Turn (User → Hermes → User)

```
1. User speaks: "um the docker thing?"
2. LiveKit STT commits text
3. IntermediaryAgent.on_user_speech_committed() fires
4. Refine: "Debug the Docker permission error" (system prompt)
5. HTTP POST to /api/chat with refined text
6. Hermes streams response chunks:
   
   Chunk 1: "First, let me check the Docker logs..."
   → Distill: "Checking the Docker logs..."
   → TTS: "Checking the Docker logs..."
   → Transcript UI: [Hermes] "First, let me check the Docker logs..."
   
   Chunk 2: "I can see a permission denied error on /var/run/docker.sock"
   → Distill: "Found a permission error on the Docker socket."
   → TTS: "Found a permission error on the Docker socket."
   → Transcript UI: [Hermes] "I can see a permission denied error..."
   
   Chunk 3: "Run: sudo usermod -aG docker $USER"
   → Distill: "Run this command to fix it."
   → TTS: "Run this command to fix it."
   → Transcript UI: [Hermes] "Run: sudo usermod -aG docker $USER"
   
   Chunk 4: {"type": "done"}
   → Check for pending steer
   → If none → done
```

### Barge-in Turn (User Steers Mid-Response)

```
1. User speaks: "no, the OTHER error"
2. STT commits text → on_user_speech_committed()
3. _is_barge_in() returns True (session.currently_speaking)
4. session.stop_speaking() — cuts TTS immediately
5. SteeringController.capture_steer(room, "no, the OTHER error")
6. self.current_generation[room] += 1
7. Transcript UI: [User] "[Steer] no, the OTHER error"
8. Hermes continues streaming (chunks are now stale but user doesn't hear them)
9. Hermes finishes: {"type": "done"}
10. SteeringController.has_pending_steer() returns True
11. Inject: "[User guidance] no, the OTHER error"
12. Hermes receives steer, adjusts course
13. Hermes streams corrected response
14. Distill → TTS → transcript UI
```

### Bottage-in Timing

| Event | Time (relative) | User Experience |
|-------|-----------------|-----------------|
| Agent starts speaking TTS | T=0 | User hears distilled response |
| User starts speaking (barge-in) | T=X | |
| VAD detects user speech | T=X+50ms | |
| `on_user_speech_committed` fires | T=X+200ms | |
| `session.stop_speaking()` called | T=X+210ms | User hears TTS cut off |
| STT commits user text | T=X+500ms | |
| Steer stored | T=X+510ms | Hermes still processing |
| Hermes finishes current step | T=Y | |
| Steer injected | T=Y+10ms | Hermes receives correction |
| Hermes responds to steer | T=Y+500ms | User hears new response |

Target: TTS cut-off within 200ms of user speech onset.

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

### Generation ID Tracking

To handle stale chunks after barge-in:

```python
# Before sending to Hermes
generation = state.next_generation()

async for chunk in hermes_client.send_message(text, session_id):
    # If barge-in happened during this stream, chunks are stale
    if state.current_generation != generation:
        # Discard stale chunk
        continue
    
    distilled = await distill(chunk)
    session.say(distilled)
```

---

## Session Mapping

LiveKit session state differs from Hermes session state:

| LiveKit | Hermes | Mapping |
|---------|--------|---------|
| Room name | — | Used as key |
| Participant identity | — | Used as user identifier |
| — | session_id | Created on participant connect |
| `currently_speaking` | — | Used for barge-in detection |
| Transcription events | — | Forwarded to frontend |

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

## Prompt Engineering

### Intermediary System Prompt

```
You are a thin intermediary between the user and Hermes (a powerful AI agent).

Your job:
1. REFINE: When user speaks in fragments or with vague references, clarify their 
   intent using conversation context before sending to Hermes.
2. DISTILL: When Hermes responds with long technical output, summarize it naturally 
   for speech.
3. STEER: When the user interrupts (barge-in), capture their correction and inject 
   it into the next exchange.

Rules:
- Preserve user intent exactly — never change what they're asking for
- Resolve pronouns ("that thing", "the error") using conversation history
- Keep distilled output to 1-2 sentences for natural speech
- If the user interrupts, stop speaking immediately and listen
- You do NOT do heavy reasoning — that's Hermes's job.

Previous topics: {intent_history}
Current focus: {current_topic}
```

### Refinement Examples

| Raw Input | Refined Output | Context Used |
|-----------|---------------|--------------|
| "um the docker thing?" | "Debug the Docker permission error" | intent_history contains "Docker permission error" |
| "no the OTHER one" | "Switch back to the container startup error" | intent_history contains both errors |
| "ok what about that?" | "Continue discussing the Docker socket permission issue" | current_topic = Docker |
| "yeah go ahead" | [pass through unchanged] | No vagueness to resolve |
| "run the thing from before" | "Run `sudo usermod -aG docker $USER` from the previous response" | Refers to prior command |

### Distillation Examples

| Raw Hermes Response | Distilled Output |
|---------------------|------------------|
| "First, let me check the Docker logs by reading /var/log/syslog to see if there are any permission-related entries." | "Checking the logs..." |
| "I can see the error: `permission denied while connecting to Docker daemon socket at unix:///var/run/docker.sock`. This means your user doesn't have access to the Docker socket." | "Found the issue — your user doesn't have access to the Docker socket." |
| "To fix this, run: `sudo usermod -aG docker $USER && newgrp docker`. This adds your user to the docker group and refreshes group membership." | "Run this command, then try Docker again." |
| `<think>Let me think about this...</think> The answer is 42. | "The answer is 42." |

---

## Frontend (Transcript UI)

### Layout

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
│  │  [Hermes] "Found a permission error..."         │ │
│  │  [Speaking] "Found a permission error!"         │ │
│  │  [You] "[Steer] no the OTHER error"             │ │
│  │  [Intermediary] → "[User guidance] the OTHER   │ │
│  │                    Docker error"                │ │
│  │  [Hermes] "Ah, you meant the container          │ │
│  │           startup error..."                     │ │
│  │  [Speaking] "Switching to container startup..." │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ ┌────────┐ │
│  │ 🎙 Mute  │  │ ⏹ Leave  │  │ 🔄 Clear │ │ ⚙      │ │
│  └──────────┘  └──────────┘  └──────────┘ └────────┘ │
└─────────────────────────────────────────────────────┘
```

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

---

## Test Strategy

### Test Types

| Type | Tool | Evidence | When |
|------|------|----------|------|
| Unit test | pytest | Terminal output | Every function |
| Integration test | pytest + mock Hermes API | Terminal output | Phase 1.2+ |
| Frontend test | Playwright | Screenshot + video | Phase 1.5+ |
| Voice test | Playwright + mic / LiveKit test mode | Video recording | Phase 1.6+ |
| E2E test | Playwright + real Hermes instance | Video recording | Phase 1.8 |

### Empirical Validation

Per `deep-think` skill: **analysis without running the system is NOT enough**. Every claim about integration behavior must be verified by actually running the components together.

### Video Evidence Requirements

For tests that involve voice or UI:

```python
# conftest.py
@pytest.fixture
async def browser():
    browser = await playwright.chromium.launch(
        record_video_dir="test-evidence/videos/",
        record_video_size={"width": 1280, "height": 720}
    )
    yield browser
    await browser.close()
```

Tests record video to `test-evidence/videos/{test-name}-{timestamp}.webm`.

### Phase 1 Test Plan

| Test | Type | Evidence | Verifies |
|------|------|----------|----------|
| `test_refinement_resolves_pronouns` | Unit | Terminal | "thing" → specific noun |
| `test_distillation_summarizes_long_response` | Unit | Terminal | 3-paragraph → 1 sentence |
| `test_hermes_client_parses_sse_stream` | Unit | Terminal | SSE parsing works |
| `test_barge_in_stops_tts` | Integration | Terminal | stop_speaking called |
| `test_steer_injected_after_hermes_finishes` | Integration | Terminal | [User guidance] prefix |
| `test_transcript_ui_updates` | Playwright | Screenshot + video | Transcript shows exchanges |
| `test_livekit_room_connection` | Playwright | Screenshot + video | User can connect to room |
| `test_voice_input_triggers_stt` | Playwright | Video | Speech → STT → Hermes query |
| `test_barge_in_cuts_tts` | Playwright | Video | User speaks → agent stops |
| `test_e2e_full_conversation` | Playwright | Video | Complete conversation flow |

---

## Integration Points

### hermes-agent Changes (minimal — NONE for Phase 1)

Phase 1 uses existing Hermes WebUI API. No changes to hermes-agent or hermes-webui required.

Future phases may need:
- Expose Hermes API via `API_SERVER_ENABLED` on gateway (for direct gateway access)
- Add WebSocket support to Hermes for real-time steer injection

But for Phase 1: **zero changes to existing repos**.

### Hermes WebUI Endpoints Used

| Endpoint | Required | Notes |
|----------|----------|-------|
| `POST /api/sessions` | Yes | Create session |
| `POST /api/api/chat` | Yes | Send message, get SSE stream |
| `POST /api/chat/steer` | Optional | Use if WebSocket injection is preferred over next-message |

### LiveKit Configuration

```bash
# LiveKit CLI for local development
livekit-server --dev

# Or LiveKit Cloud (production)
# Set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
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
- No PII in intermediary logs at INFO level (only DEBUG + redicated)

---

## Repo Structure (final)

```
intermediary-agent/
├── README.md
├── PLAN.md
├── ROADMAP.md
├── INTEGRATION.md
├── pyproject.toml
├── intermediary/
│   ├── __init__.py
│   ├── agent.py
│   ├── hermes_client.py
│   ├── refinement.py
│   ├── distillation.py
│   ├── steering.py
│   ├── session.py
│   ├── prompts.py
│   └── audio_config.py
├── audio/
│   ├── __init__.py
│   ├── base.py
│   ├── livekit_native.py
│   ├── ten_backend.py
│   ├── pipecat_backend.py
│   └── discord_bridge.py
├── webui/
│   ├── __init__.py
│   ├── app.py
│   ├── static/
│   │   ├── transcript.js
│   │   └── styles.css
│   └── templates/
│       └── index.html
├── tests/
│   ├── conftest.py
│   ├── test_refinement.py
│   ├── test_distillation.py
│   ├── test_steering.py
│   ├── test_hermes_client.py
│   ├── test_agent.py
│   ├── test_transcript_ui.py
│   └── test_e2e.py
├── test-evidence/
│   ├── videos/
│   └── screenshots/
└── scripts/
    ├── dev.sh
    └── doctor.sh
```
