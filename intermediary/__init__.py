"""Intermediary Agent — LiveKit-based voice intermediary between human and Hermes."""

__version__ = "0.1.0"

from .agent import IntermediaryAgent
from .hermes_client import HermesClient
from .session import SessionState, SessionManager
from .distillation import DistillationBuffer, distill
from .steering import BargeInStateMachine

__all__ = [
    "IntermediaryAgent",
    "HermesClient",
    "SessionState",
    "SessionManager",
    "DistillationBuffer",
    "distill",
    "BargeInStateMachine",
]
