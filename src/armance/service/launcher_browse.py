"""Server-side folder browser for the launcher's "new project" picker.

The web client cannot open a native folder dialog onto the server's
filesystem, so the launcher offers a minimal in-UI explorer backed by this
module. The server runs on the user's own machine, so listing local
directories is safe **as long as it stays confined to a root** — this module
rejects path-traversal and symlink escapes outside that root.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class BrowseError(ValueError):
    """Raised when a requested path is invalid or escapes the allowed root."""


def _confined_resolve(path: Path, root: Path) -> Path:
    """Resolve *path* and assert it stays within *root* (symlinks included)."""
    real_root = root.resolve()
    # ``strict=True`` resolves symlinks and raises if the path is missing, so a
    # symlink pointing outside resolves to its real (outside) target and fails
    # the containment check below.
    try:
        real = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise BrowseError(f"path does not exist: {path}") from exc
    if real != real_root and real_root not in real.parents:
        raise BrowseError(f"path escapes root: {path}")
    if not real.is_dir():
        raise BrowseError(f"not a directory: {path}")
    return real


def browse(path: Path, root: Path) -> dict[str, Any]:
    """List immediate subdirectories of *path*, confined to *root*.

    Returns ``{"path": <resolved str>, "root": <resolved str>,
    "dirs": [{"name", "path"}], "parent": <str | None>}``. Files are omitted.
    Raises :class:`BrowseError` on traversal / symlink escape / missing path.
    """
    real = _confined_resolve(path, root)
    real_root = root.resolve()

    dirs: list[dict[str, str]] = []
    for child in sorted(real.iterdir(), key=lambda p: p.name.lower()):
        try:
            if child.is_dir() and not child.name.startswith("."):
                # Skip symlinks that escape the root rather than fail the listing.
                resolved_child = child.resolve(strict=True)
                if resolved_child != real_root and real_root not in resolved_child.parents:
                    continue
                dirs.append({"name": child.name, "path": str(child)})
        except OSError:
            continue

    parent = str(real.parent) if real != real_root else None
    return {
        "path": str(real),
        "root": str(real_root),
        "parent": parent,
        "dirs": dirs,
    }
