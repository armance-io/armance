"""armance.platform.sessions — SessionRegistry ABC.

V2 implementation: InMemorySessionRegistry (see J.2).
V3 swap: FirestoreSessionRegistry — see issues/features/web-v3-saas-readiness.md.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# SessionEntry is defined here as a forward-compatible type alias.
# J.2 will replace this with a proper dataclass carrying
# (Session, LoopContext, EventBus, WebCheckpointHandler).
SessionEntry = Any


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
