"""Library state: distinct tracking of *indexed* (RAG-searchable) vs *read*
(loaded into every agent's context for this session / persistently).

- `vector/manifest.json` (existing) — indexed = doc is in the RAG library
  (chunked, embedded, searchable). Owned by ingestion.sync_docs.
- `vector/read.json` (new) — read = doc's full text is force-injected into
  every host-agent system prompt. Two modes:
    * session-only (default): a per-session list in SessionState.metadata
      under `library_read_session`
    * persistent: a project-level set in `.armance/vector/read.json`

The union of (persistent ∪ session-only) is what we inject.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_READ_FILE = "read.json"


def _read_path(armance_root: Path) -> Path:
    return armance_root / "vector" / _READ_FILE


def load_persistent_read(armance_root: Path) -> set[str]:
    p = _read_path(armance_root)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text(encoding="utf-8")) or [])
    except Exception:
        logger.warning("read.json malformed; resetting to empty", exc_info=True)
        return set()


def save_persistent_read(armance_root: Path, items: set[str]) -> None:
    p = _read_path(armance_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(items), indent=2), encoding="utf-8")


def mark_read(armance_root: Path, filename: str, *, persist: bool, session_meta: dict) -> None:
    if persist:
        items = load_persistent_read(armance_root)
        items.add(filename)
        save_persistent_read(armance_root, items)
    else:
        cur = list(session_meta.get("library_read_session", []))
        if filename not in cur:
            cur.append(filename)
        session_meta["library_read_session"] = cur


def unmark_read(armance_root: Path, filename: str, session_meta: dict) -> bool:
    """Remove from both persistent and session lists. Returns True if anything removed."""
    removed = False
    items = load_persistent_read(armance_root)
    if filename in items:
        items.discard(filename)
        save_persistent_read(armance_root, items)
        removed = True
    cur = list(session_meta.get("library_read_session", []))
    if filename in cur:
        cur = [x for x in cur if x != filename]
        session_meta["library_read_session"] = cur
        removed = True
    return removed


def effective_read_set(armance_root: Path, session_meta: dict) -> set[str]:
    """Union of persistent and session-only read docs."""
    return load_persistent_read(armance_root) | set(session_meta.get("library_read_session", []))


def is_persistent_read(armance_root: Path, filename: str) -> bool:
    return filename in load_persistent_read(armance_root)
