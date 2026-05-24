"""armance.platform — V2 platform abstractions.

Four thin ABCs that decouple the service layer from its execution environment:

  Storage          — file / object storage (local → GCS in V3)
  SessionRegistry  — in-memory session catalogue (local → Firestore in V3)
  EventBus         — ordered event stream (local queue → Pub/Sub in V3)
  WorkflowExecutor — async task runner (in-process → Cloud Tasks in V3)

Each ABC is defined in its own sub-module; this package re-exports all four
plus the ``get_current_user`` FastAPI dependency stub.

V3 swap points are documented in the V3 forward-spec (internal).

Layer rule
----------
``armance.platform`` sits **alongside** ``armance.transport`` as a boundary
the service layer crosses.  It may only import from ``armance.core``.
It must **never** import from ``armance.service`` or ``armance.client``.
The import-linter contract in ``.importlinter`` (contract: platform-limits)
enforces this at CI time.
"""
from __future__ import annotations

from armance.platform.events import EventBus
from armance.platform.executor import WorkflowExecutor
from armance.platform.sessions import InMemorySessionRegistry, SessionEntry, SessionRegistry
from armance.platform.storage import LocalFilesystemStorage, Storage
from armance.platform.user import get_current_user

__all__ = [
    "EventBus",
    "InMemorySessionRegistry",
    "LocalFilesystemStorage",
    "SessionEntry",
    "SessionRegistry",
    "Storage",
    "WorkflowExecutor",
    "get_current_user",
]
