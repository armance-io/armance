"""armance.platform.sessions — SessionRegistry ABC + InMemorySessionRegistry.

V2 implementation: InMemorySessionRegistry.
V3 swap: FirestoreSessionRegistry — see the V3 forward-spec (internal).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class SessionEntry:
    """A registry entry for one (project_id, sid) pair.

    Carries the minimal metadata the registry needs to manage the session.
    J.2 uses a plain dataclass; V3 may extend this with ORM fields for
    Firestore persistence.

    Additional runtime objects (Session, LoopContext, EventBus,
    WebCheckpointHandler) can be attached to ``data`` by callers.
    """

    project_id: str
    sid: str
    data: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SessionRegistry(Protocol):
    """Abstract session catalogue.

    Creates, retrieves, lists, and deletes session entries keyed by
    ``(project_id, session_id)``.

    The in-memory implementation (V2) stores entries in a plain dict.
    The Firestore implementation (V3) persists the index and rehydrates
    entries from Storage on demand.
    """

    async def create(self, project_id: str) -> str:
        """Create a new session for *project_id* and return its sid."""
        ...

    async def get(self, project_id: str, sid: str) -> SessionEntry | None:
        """Return the entry for *(project_id, sid)*, or ``None`` if absent."""
        ...

    async def list(self, project_id: str) -> list[str]:
        """Return all session ids for *project_id*."""
        ...

    async def delete(self, project_id: str, sid: str) -> None:
        """Remove the entry for *(project_id, sid)*."""
        ...


class InMemorySessionRegistry:
    """V2 SessionRegistry backed by a plain in-process dict.

    Keys are ``(project_id, sid)`` tuples.  Session IDs are UUID4 hex
    strings (12 chars).  This implementation is not thread-safe; for V2
    single-user local operation that is acceptable.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], SessionEntry] = {}

    async def create(self, project_id: str) -> str:
        sid = uuid.uuid4().hex[:12]
        self._store[(project_id, sid)] = SessionEntry(
            project_id=project_id, sid=sid
        )
        return sid

    async def get(self, project_id: str, sid: str) -> SessionEntry | None:
        return self._store.get((project_id, sid))

    async def list(self, project_id: str) -> list[str]:
        return [
            entry.sid
            for (pid, _), entry in self._store.items()
            if pid == project_id
        ]

    async def delete(self, project_id: str, sid: str) -> None:
        self._store.pop((project_id, sid), None)
