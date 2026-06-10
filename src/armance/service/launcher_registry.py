"""Global project registry for the grandma launcher.

Tracks known project folders in ``~/.config/armance/projects.json`` so the
launcher can list recent projects. One source of truth; data folders stay
per-project. Entries are kept even when their path disappears (flagged
``exists: false``) until the user removes them.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from armance import paths

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pid_for(resolved_path: str) -> str:
    """Stable, URL-safe project id: slugified folder name + path hash.

    The hash makes the pid unique even when two folders share a basename, and
    stable across restarts (derived only from the absolute path).
    """
    name = Path(resolved_path).name
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"
    digest = hashlib.sha1(resolved_path.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


def _read_raw() -> dict[str, list[dict[str, Any]]]:
    registry_file = paths.projects_registry_path()
    if not registry_file.exists():
        return {"projects": []}
    try:
        data = json.loads(registry_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
            raise ValueError("malformed registry")
        return data
    except Exception:
        logger.exception("corrupt projects registry — starting fresh")
        return {"projects": []}


def _write_raw(data: dict[str, list[dict[str, Any]]]) -> None:
    registry_file = paths.projects_registry_path()
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".tmp", prefix="projects_", dir=registry_file.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, registry_file)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def bump_project(folder: Path) -> None:
    """Register *folder* (or refresh its ``last_opened``)."""
    resolved = str(Path(folder).resolve())
    data = _read_raw()
    now = _now_iso()
    for entry in data["projects"]:
        if entry.get("path") == resolved:
            entry["last_opened"] = now
            break
    else:
        data["projects"].append(
            {
                "id": _pid_for(resolved),
                "path": resolved,
                "name": Path(resolved).name,
                "last_opened": now,
            }
        )
    _write_raw(data)


def remove_project(folder: Path) -> bool:
    """Drop *folder* from the registry. Returns True if it was present."""
    resolved = str(Path(folder).resolve())
    data = _read_raw()
    before = len(data["projects"])
    data["projects"] = [e for e in data["projects"] if e.get("path") != resolved]
    if len(data["projects"]) != before:
        _write_raw(data)
        return True
    return False


def list_projects() -> list[dict[str, Any]]:
    """Return known projects, most-recent first, with a live ``exists`` flag."""
    data = _read_raw()
    items = [
        {
            "id": e.get("id") or _pid_for(e.get("path", "")),
            "name": e.get("name", Path(e.get("path", "")).name),
            "path": e.get("path", ""),
            "last_opened": e.get("last_opened", ""),
            "exists": Path(e.get("path", "")).is_dir(),
        }
        for e in data["projects"]
    ]
    items.sort(key=lambda e: e["last_opened"], reverse=True)
    return items


def path_for_pid(pid: str) -> Path | None:
    """Resolve a registry pid to its project folder, or None if unknown.

    pids resolve ONLY through the registry — a raw pid never builds an
    arbitrary filesystem path. Unknown pid → None (callers raise 404).
    """
    data = _read_raw()
    for e in data["projects"]:
        eid = e.get("id") or _pid_for(e.get("path", ""))
        if eid == pid:
            p = e.get("path", "")
            return Path(p).resolve() if p else None
    return None
