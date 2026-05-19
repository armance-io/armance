"""Shared TUI types — re-exported from service layer for compatibility.

This module acts as a bridge so that existing client-side imports from
armance.client.tui.types do not break, while keeping actual domain logic
and structures defined strictly in the service layer.
"""
from __future__ import annotations

from armance.service.help_text import COMMANDS, build_help_text
from armance.service.checkpoint import CheckpointAbort
from armance.service.loop_context import AgentStatus, LoopContext

# Compatibility re-exports
__all__ = [
    "COMMANDS",
    "build_help_text",
    "CheckpointAbort",
    "AgentStatus",
    "LoopContext",
]
