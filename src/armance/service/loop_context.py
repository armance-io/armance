"""LoopContext and AgentStatus service definitions.

Decouples loop state structure from the client/TUI package.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from armance.config import Config
    from armance.platform.events import EventBus
    from armance.service.llm_service import TokenLedger
    from armance.service.session import SessionState, Session
    from armance.service.checkpoint import CheckpointHandler


@dataclass(slots=True)
class AgentStatus:
    """Snapshot of an agent's runtime state."""
    name: str
    state: str = "idle"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


@dataclass
class LoopContext:
    """Shared context passed to all slash-command handlers."""
    armance_root: Path
    cfg: Config
    state: SessionState
    session: Session
    ledger: TokenLedger
    statuses: list[AgentStatus]
    agents: list  # list[Agent]
    output_lines: list[str] = field(default_factory=list)
    _pending_lines: list[str] = field(default_factory=list)
    effort: str = "medium"
    _last_output: str = ""
    _deliverable_confirmation: dict | None = None
    checkpoint_handler: CheckpointHandler | None = None
    # Optional event bus — populated by the web backend; None in the TUI.
    # When set, service handlers may emit web-bound events (agents_proposed,
    # agent_streaming_*, etc.) without coupling to the FastAPI layer.
    event_bus: EventBus | None = None

    def append(self, text: str) -> None:
        lines = text.splitlines()
        self.output_lines.extend(lines)
        self._pending_lines.extend(lines)
        if len(self.output_lines) > 200:
            self.output_lines = self.output_lines[-200:]
        self._last_output = text
