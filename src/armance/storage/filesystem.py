"""Storage layer protocol and filesystem implementation.

This module provides the Storage protocol and FilesystemStorage
implementation for all file I/O operations in Armance.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


class Storage(Protocol):
    """Protocol for all storage implementations."""

    async def read_text(self, path: Path) -> str:
        """Read text file content."""
        ...

    async def write_text(self, path: Path, content: str) -> Path:
        """Write text to file atomically (tmp + rename)."""
        ...

    async def read_bytes(self, path: Path) -> bytes:
        """Read binary file content."""
        ...

    async def write_bytes(self, path: Path, content: bytes) -> Path:
        """Write binary to file atomically."""
        ...

    async def exists(self, path: Path) -> bool:
        """Check if path exists."""
        ...

    async def list_dir(self, path: Path) -> list[Path]:
        """List directory contents."""
        ...

    async def delete(self, path: Path) -> None:
        """Delete a file."""
        ...

    async def mkdir(self, path: Path, parents: bool = False) -> None:
        """Create directory."""
        ...


class FilesystemStorage(Storage):
    """Filesystem-based storage implementation with atomic writes."""

    def __init__(self, root: Path) -> None:
        self._root = root
        logger.info("FilesystemStorage initialized for %s", root)

    @property
    def root(self) -> Path:
        """Get the storage root directory."""
        return self._root

    async def read_text(self, path: Path) -> str:
        """Read text file content."""
        full_path = self._root / path
        return full_path.read_text(encoding="utf-8")

    async def write_text(self, path: Path, content: str) -> Path:
        """Write text to file atomically (tmp + rename)."""
        full_path = self._root / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file then rename
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=full_path.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            tmp_path.replace(full_path)
            logger.debug("Wrote %s", full_path)
            return full_path
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    async def read_bytes(self, path: Path) -> bytes:
        """Read binary file content."""
        full_path = self._root / path
        return full_path.read_bytes()

    async def write_bytes(self, path: Path, content: bytes) -> Path:
        """Write binary to file atomically."""
        full_path = self._root / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=full_path.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            tmp_path.replace(full_path)
            logger.debug("Wrote %s", full_path)
            return full_path
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    async def exists(self, path: Path) -> bool:
        """Check if path exists."""
        full_path = self._root / path
        return full_path.exists()

    async def list_dir(self, path: Path) -> list[Path]:
        """List directory contents."""
        full_path = self._root / path
        if not full_path.exists():
            return []
        return list(full_path.iterdir())

    async def delete(self, path: Path) -> None:
        """Delete a file."""
        full_path = self._root / path
        if full_path.exists():
            full_path.unlink()
            logger.debug("Deleted %s", full_path)

    async def mkdir(self, path: Path, parents: bool = False) -> None:
        """Create directory."""
        full_path = self._root / path
        full_path.mkdir(parents=parents, exist_ok=True)
