"""armance.platform.storage — Storage ABC.

V2 implementation: LocalFilesystemStorage (see J.1).
V3 swap: GcsStorage — see issues/features/web-v3-saas-readiness.md.
"""
from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class Storage(Protocol):
    """Abstract key/value object store.

    Keys use forward-slash paths (``projects/<pid>/sessions/<sid>/state.json``).
    The local implementation maps them to ``<armance_root>/<key>``.
    The GCS implementation (V3) maps them to ``gs://<bucket>/<key>``.

    All methods are async to allow non-blocking I/O on every backend.
    """

    async def read_bytes(self, key: str) -> bytes: ...

    async def write_bytes(self, key: str, data: bytes) -> None: ...

    async def read_text(self, key: str) -> str: ...

    async def write_text(self, key: str, text: str) -> None: ...

    async def exists(self, key: str) -> bool: ...

    async def list(self, prefix: str) -> list[str]: ...

    async def delete(self, key: str) -> None: ...

    async def read_jsonl(self, key: str) -> AsyncIterator[dict]: ...  # type: ignore[misc]
