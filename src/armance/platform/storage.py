"""armance.platform.storage — Storage ABC + LocalFilesystemStorage.

V2 implementation: LocalFilesystemStorage.
V3 swap: GcsStorage — see the V3 forward-spec (internal).
"""
from __future__ import annotations

import json
from pathlib import Path
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


class LocalFilesystemStorage:
    """V2 Storage implementation backed by the local filesystem.

    All keys are resolved relative to *root*.  Path-traversal attempts
    (keys whose resolved path escapes *root*) raise ``ValueError``.

    This class is intentionally synchronous under the hood — the overhead
    of thread-pooling tiny files is not worth the complexity for V2.
    Async wrappers satisfy the protocol signature.
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve(self, key: str) -> Path:
        """Resolve *key* to an absolute path, rejecting traversal attempts."""
        # Normalise to POSIX-style, strip leading slash so Path doesn't
        # interpret it as absolute.
        clean = key.lstrip("/")
        resolved = (self._root / clean).resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError:
            raise ValueError(
                f"Path traversal detected: key {key!r} escapes storage root"
            )
        return resolved

    # ------------------------------------------------------------------
    # Protocol implementation
    # ------------------------------------------------------------------

    async def read_bytes(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    async def write_bytes(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def read_text(self, key: str) -> str:
        return self._resolve(key).read_text(encoding="utf-8")

    async def write_text(self, key: str, text: str) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    async def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    async def list(self, prefix: str) -> list[str]:
        """Return all file keys whose path starts with *prefix*.

        The prefix is resolved to a directory; if it doesn't exist, an
        empty list is returned.  Keys are returned as forward-slash paths
        relative to *root*.
        """
        prefix_path = self._resolve(prefix)
        if not prefix_path.exists():
            return []
        results: list[str] = []
        for p in prefix_path.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self._root)
                results.append(rel.as_posix())
        return sorted(results)

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()

    async def read_jsonl(self, key: str) -> AsyncIterator[dict]:  # type: ignore[override]
        """Yield each non-empty JSON line from *key* as a dict."""
        text = self._resolve(key).read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                yield json.loads(stripped)
