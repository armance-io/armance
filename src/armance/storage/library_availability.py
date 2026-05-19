"""Library availability detection.

The "library" (= RAG-searchable corpus) is only available when an
embedding provider + model is configured AND the client can actually
initialise. This module exposes a single is_library_available(cfg) ->
bool the meta-agents and TUI rely on to:

  - Armance: never propose 'indexer' if the library is inactive.
  - TUI sidebar: render an active/inactive badge with doc + slip counts.
  - Malik / Kim: skip library-status prompts when there's no library.

Two complementary signals:
  1. Config has embedding_provider + embedding_model set.
  2. The corresponding LLMClient initialises without raising.

We do not call the network here — initialising the client is cheap; an
actual embed test happens lazily at /library index time.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from armance.config import Config

logger = logging.getLogger(__name__)


def is_library_available(cfg: "Config | None") -> bool:
    """True when the embedding stack is configured and initialisable."""
    if cfg is None:
        return False
    provider = getattr(cfg, "embedding_provider", "") or ""
    model = getattr(cfg, "embedding_model", "") or ""
    if not provider or not model:
        return False
    try:
        from armance.core.protocols.llm import get_client
        get_client(provider, cfg)
    except Exception:
        logger.debug("library unavailable: client init failed", exc_info=True)
        return False
    return True


def library_summary(armance_root: Path, cfg: "Config | None") -> dict:
    """Return a compact snapshot for sidebar / agent prompts:

        {
          "active": bool,
          "provider": str,
          "model": str,
          "docs": int,         # indexed docs (manifest)
          "chunks": int,       # total slips in sqlite-vec
        }
    """
    active = is_library_available(cfg)
    out = {
        "active": active,
        "provider": getattr(cfg, "embedding_provider", "") if cfg else "",
        "model": getattr(cfg, "embedding_model", "") if cfg else "",
        "docs": 0,
        "chunks": 0,
    }
    if not active:
        return out
    try:
        from armance.storage.rag_status import get_rag_status
        status = get_rag_status(armance_root, cfg)
        out["docs"] = sum(1 for d in status["docs_on_disk"] if d["in_db"])
        out["chunks"] = int(status.get("total_chunks", 0) or 0)
    except Exception:
        logger.debug("library_summary status read failed", exc_info=True)
    return out
