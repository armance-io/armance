"""AppState — wires SessionRegistry + EventBus factory.

Holds all live sessions for the lifetime of the FastAPI process.
A SessionEntry here is richer than the platform SessionEntry: it carries
the full (Session, LoopContext, LocalEventBus, WebCheckpointHandler) tuple
needed to serve web requests.

V2 is single-user / single-project (pid = "default").
V3 SaaS wires real project isolation on top without touching this module.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from armance.platform.sessions import InMemorySessionRegistry

if TYPE_CHECKING:
    from armance.service.loop_context import LoopContext
    from armance.service.session import Session
    from armance.platform.events import LocalEventBus
    from backend.checkpoint import WebCheckpointHandler

logger = logging.getLogger(__name__)


@dataclass
class WebSession:
    """All runtime objects bound to one (project_id, sid) pair."""

    sid: str
    project_id: str
    session: "Session"
    ctx: "LoopContext"
    bus: "LocalEventBus"
    handler: "WebCheckpointHandler"
    # driver_client_id: the client that initiated the session (read-along guard)
    driver_client_id: str | None = None


class AppState:
    """Process-level singleton that owns all live WebSessions.

    Instantiated once in the FastAPI lifespan; injected as app.state.
    """

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root
        self.registry = InMemorySessionRegistry()
        self._sessions: dict[str, WebSession] = {}

    def put(self, web_session: WebSession) -> None:
        self._sessions[web_session.sid] = web_session

    def get(self, sid: str) -> WebSession | None:
        return self._sessions.get(sid)

    def delete(self, sid: str) -> None:
        self._sessions.pop(sid, None)

    def all_sids(self) -> list[str]:
        return list(self._sessions.keys())
