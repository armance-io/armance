"""Structured library actions for non-conversational callers (the web UI).

The `/library` slash command (``library_ops.dispatch``) returns localized
markdown meant to land inside the conversation. A button click in the web
library needs a machine-readable success/failure signal instead, so it can
show an ephemeral check on success and an elegant error on failure without
polluting the conversation or running an LLM turn.

This module is the single entry point for that: ``run_library_action``.
"""
from __future__ import annotations

import asyncio
import logging

from armance.service.library_ops import _find_doc, dispatch
from armance.service.loop_context import LoopContext

logger = logging.getLogger(__name__)

_STATE_ACTIONS = ("load", "unload", "unindex")


async def run_library_action(action: str, name: str | None, ctx: LoopContext) -> dict:
    """Run a library action and return ``{ok, message, error}``.

    ``index`` carries precise failure detection (sync_docs result codes); the
    cheap state ops (load/unload/unindex) reuse ``dispatch`` for their
    localized message and report failure only on a raised exception.
    """
    from armance.nls import t

    sub = (action or "").lower()
    args = [name] if name else []

    if sub == "index":
        return await _index(args, ctx)

    if sub not in _STATE_ACTIONS:
        return {"ok": False, "message": t("library.unknown_sub", sub=sub), "error": "unknown_action"}

    try:
        message = await dispatch([sub, *args], ctx)
    except Exception as exc:  # noqa: BLE001 — surface any storage failure to the UI
        logger.exception("library action %s failed", sub)
        return {"ok": False, "message": str(exc), "error": "action_failed"}
    return {"ok": True, "message": message, "error": None}


async def _index(args: list[str], ctx: LoopContext) -> dict:
    from armance.nls import t
    from armance.storage.ingestion import sync_docs

    if args and args[0] and args[0] not in ("--all", "all"):
        filename = " ".join(args).strip()
        if _find_doc(ctx.armance_root, filename) is None:
            return {"ok": False, "message": t("load.not_found", filename=filename), "error": "not_found"}

    try:
        result = await asyncio.to_thread(sync_docs, ctx.armance_root, config=ctx.cfg)
    except Exception as exc:  # noqa: BLE001
        logger.exception("library index failed")
        return {"ok": False, "message": t("ingest.failed", error=str(exc)), "error": "index_failed"}

    if result.get("error") == "embed_init_failed":
        return {"ok": False, "message": t("ingest.embed_init_failed"), "error": "embed_init_failed"}

    indexed = result.get("indexed", 0)
    chunks = result.get("chunks", 0)
    skipped = result.get("skipped", 0)
    deleted = result.get("deleted", 0)
    # Per-doc chunk counts → the names actually (re)indexed, for the UI to
    # surface one "<doc> indexed" toast per document.
    per_doc = result.get("per_doc_chunks") or {}
    indexed_docs = sorted(per_doc.keys())
    if indexed == 0 and skipped == 0 and deleted == 0:
        return {"ok": True, "message": t("ingest.nothing_to_do"), "error": None, "indexed_docs": []}

    parts: list[str] = []
    if indexed:
        parts.append(t("ingest.part_indexed", n=indexed))
        if chunks:
            parts.append(t("ingest.part_chunks", n=chunks))
    if skipped:
        parts.append(t("ingest.part_skipped", n=skipped))
    if deleted:
        parts.append(t("ingest.part_deleted", n=deleted))
    return {"ok": True, "message": " ; ".join(parts) + ".", "error": None, "indexed_docs": indexed_docs}
