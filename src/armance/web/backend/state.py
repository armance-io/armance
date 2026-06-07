"""AppState — wires SessionRegistry + EventBus factory.

Holds all live sessions for the lifetime of the FastAPI process.
A SessionEntry here is richer than the platform SessionEntry: it carries
the full (Session, LoopContext, LocalEventBus, WebCheckpointHandler) tuple
needed to serve web requests.

V2 is single-user / single-project (pid = "default").
V3 SaaS wires real project isolation on top without touching this module.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from armance.platform.sessions import InMemorySessionRegistry

if TYPE_CHECKING:
    from armance.service.loop_context import LoopContext
    from armance.service.session import Session
    from armance.platform.events import LocalEventBus
    from armance.web.backend.checkpoint import WebCheckpointHandler

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
    # The in-flight workflow run task (None when idle). A workflow run executes
    # in the background so POST /run returns immediately and HITL checkpoints can
    # be resolved by separate POST /checkpoint requests while the run is paused.
    run_task: Optional["asyncio.Task[object]"] = field(default=None)


class AppState:
    """Process-level singleton that owns all live WebSessions.

    Instantiated once in the FastAPI lifespan; injected as app.state.
    """

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root
        self.registry = InMemorySessionRegistry()
        self._sessions: dict[str, WebSession] = {}

    def resolve_root(self, pid: str) -> Path | None:
        """Resolve the ``.armance`` data root for project *pid*.

        Multi-project (grandma launcher): ``default`` / empty keeps the boot
        root (single-project + ``armance web <folder>`` unchanged). A registry
        pid resolves to that project's ``<folder>/.armance``. An unknown pid
        returns None (the route raises 404) — a raw pid never addresses an
        arbitrary folder.
        """
        if pid in ("default", ""):
            return self.armance_root
        from armance.service import launcher_registry

        folder = launcher_registry.path_for_pid(pid)
        if folder is None:
            return None
        from armance import paths

        return paths.local_data_dir(folder)

    def put(self, web_session: WebSession) -> None:
        self._sessions[web_session.sid] = web_session

    def get(self, sid: str) -> WebSession | None:
        return self._sessions.get(sid)

    def delete(self, sid: str) -> None:
        self._sessions.pop(sid, None)

    def all_sids(self) -> list[str]:
        return list(self._sessions.keys())
