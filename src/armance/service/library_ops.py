"""Library command handlers — extracted from service/handlers.py.

The `/library` slash command is the single entry point for every action
on the document library (indexed slips) and the read set (full-text
loaded docs). The intercept helper for `[EXECUTE:/library-status]`
(plus the legacy `/rag-status` alias) also lives here.
"""
from __future__ import annotations

import logging
from pathlib import Path

from armance.service.loop_context import LoopContext

logger = logging.getLogger(__name__)


def _find_doc(armance_root: Path, filename: str) -> Path | None:
    docs_dir = armance_root / "docs"
    if not docs_dir.exists():
        return None
    for f in docs_dir.rglob("*"):
        if f.is_file() and f.name == filename:
            return f
    return None


async def cmd_library(args: list[str], ctx: LoopContext) -> str:
    """Unified /library command — see dispatch for subcommands."""
    return await dispatch(args, ctx)


async def dispatch(args: list[str], ctx: LoopContext) -> str:
    from armance.nls import t
    if not args:
        return await _status(ctx)
    sub = args[0].lower()
    rest = args[1:]
    if sub == "status":
        return await _status(ctx)
    if sub == "scan":
        return await _scan(ctx)
    if sub == "index":
        return await _index(rest, ctx)
    if sub == "unindex":
        return await _unindex(rest, ctx)
    if sub == "load":
        return await _load(rest, ctx)
    if sub == "unload":
        return await _unload(rest, ctx)
    return t("library.unknown_sub", sub=sub)


async def _status(ctx: LoopContext) -> str:
    """Render library status: indexed + read state."""
    from armance.nls import t
    from armance.storage.rag_status import get_rag_status, format_rag_status_markdown
    from armance.storage.library_state import effective_read_set
    status = get_rag_status(ctx.armance_root, ctx.cfg)
    md = format_rag_status_markdown(status)
    read_set = effective_read_set(ctx.armance_root, ctx.session.metadata)
    if read_set:
        md += "\n\n" + t("library.read_header") + "\n"
        for name in sorted(read_set):
            md += t("library.read_line", name=name) + "\n"
    return md


async def _scan(ctx: LoopContext) -> str:
    from armance.nls import t
    from armance.storage.rag_status import get_rag_status
    status = get_rag_status(ctx.armance_root, ctx.cfg)
    lines = [t("scan.title")]
    unread = [d["name"] for d in status["docs_on_disk"] if not d["in_db"]]
    stale = [d["name"] for d in status["docs_on_disk"] if d["stale"]]
    orphans = status["orphans"]
    if not unread and not stale and not orphans:
        lines.append(t("scan.all_clean"))
        return "\n".join(lines)
    if unread:
        lines.append("")
        lines.append(t("scan.unread_header"))
        for n in unread:
            lines.append(f"- `{n}`")
    if stale:
        lines.append("")
        lines.append(t("scan.stale_header"))
        for n in stale:
            lines.append(f"- `{n}`")
    if orphans:
        lines.append("")
        lines.append(t("scan.orphans_header"))
        for n in orphans:
            lines.append(t("scan.orphan_line", name=n))
    return "\n".join(lines)


async def _index(args: list[str], ctx: LoopContext) -> str:
    """Index doc(s) into the searchable library.

    `/library index <filename>` — index that one file (force a single-file sync).
    `/library index` or `/library index --all` — index all new/changed docs.

    sync_docs is sync (httpx embed + sqlite-vec writes). Runs in a worker
    thread so the TUI event loop and spinner keep ticking.
    """
    import asyncio

    from armance.nls import t
    from armance.storage.ingestion import sync_docs
    if args and args[0] not in ("--all", "all"):
        filename = " ".join(args).strip()
        target = _find_doc(ctx.armance_root, filename)
        if target is None:
            return t("system.error", body=t("load.not_found", filename=filename))
    try:
        result = await asyncio.to_thread(sync_docs, ctx.armance_root, config=ctx.cfg)
    except Exception as exc:
        logger.exception("library index failed")
        return t("system.error", body=t("ingest.failed", error=str(exc)))
    if result.get("error") == "embed_init_failed":
        return t("system.error", body=t("ingest.embed_init_failed"))
    indexed = result.get("indexed", 0)
    skipped = result.get("skipped", 0)
    deleted = result.get("deleted", 0)
    if indexed == 0 and skipped == 0 and deleted == 0:
        docs_dir = ctx.armance_root / "docs"
        has_files = docs_dir.exists() and any(
            p.is_file() and p.suffix.lower() in (".pdf", ".md", ".txt", ".docx")
            for p in docs_dir.rglob("*")
        )
        if has_files:
            return t("system.info", body=t("ingest.nothing_to_do"))
        return t("system.info", body=t("ingest.no_docs"))
    parts: list[str] = []
    chunks = result.get("chunks", 0)
    if indexed:
        parts.append(t("ingest.part_indexed", n=indexed))
        if chunks:
            parts.append(t("ingest.part_chunks", n=chunks))
    if skipped:
        parts.append(t("ingest.part_skipped", n=skipped))
    if deleted:
        parts.append(t("ingest.part_deleted", n=deleted))
    body = " ; ".join(parts) + ". " + t("ingest.success_suffix")
    per = result.get("per_doc_chunks") or {}
    if per:
        body += "\n" + "\n".join(
            t("ingest.per_doc_line", name=n, chunks=c)
            for n, c in sorted(per.items())
        )
    return t("system.ok", body=body)


async def _unindex(args: list[str], ctx: LoopContext) -> str:
    from armance.nls import t
    if not args:
        return t("library.unindex_usage")
    filename = " ".join(args).strip()
    from armance.storage.rag_status import forget_doc
    return forget_doc(ctx.armance_root, filename)


async def _load(args: list[str], ctx: LoopContext) -> str:
    """Mark a doc as 'read' — full text injected into every agent's context.

    Default: session-only.
    `--persist` flag: also write to vector/read.json so it survives restarts.
    """
    from armance.nls import t
    from armance.storage.library_state import mark_read
    persist = False
    cleaned: list[str] = []
    for a in args:
        if a in ("--persist", "-p", "--persistent"):
            persist = True
        else:
            cleaned.append(a)
    if not cleaned:
        return t("library.load_usage")
    filename = " ".join(cleaned).strip()
    target = _find_doc(ctx.armance_root, filename)
    if target is None:
        return t("system.error", body=t("load.not_found", filename=filename))
    mark_read(
        ctx.armance_root,
        filename,
        persist=persist,
        session_meta=ctx.session.metadata,
    )
    pending = list(ctx.session.metadata.get("host_pending_load", []))
    if filename not in pending:
        pending.append(filename)
    ctx.session.metadata["host_pending_load"] = pending
    ctx.session.save()
    if persist:
        return t("library.load_ok_persist", filename=filename)
    return t("library.load_ok_session", filename=filename)


async def _unload(args: list[str], ctx: LoopContext) -> str:
    from armance.nls import t
    from armance.storage.library_state import unmark_read
    if not args:
        return t("library.unload_usage")
    filename = " ".join(args).strip()
    removed = unmark_read(ctx.armance_root, filename, ctx.session.metadata)
    ctx.session.save()
    if removed:
        return t("library.unload_ok", filename=filename)
    return t("system.info", body=t("library.unload_not_loaded", filename=filename))


def intercept_library_status(reply: str, ctx: LoopContext) -> str:
    """If reply contains [EXECUTE:/library-status] (or legacy /rag-status),
    replace the tag with the library status report."""
    from armance.nls import t
    tag = None
    for candidate in ("[EXECUTE:/library-status]", "[EXECUTE:/rag-status]"):
        if candidate in reply:
            tag = candidate
            break
    if tag is None:
        return reply
    reply = reply.replace(tag, "").strip()
    from armance.storage.rag_status import get_rag_status, format_rag_status_markdown
    from armance.storage.library_state import effective_read_set
    try:
        status = get_rag_status(ctx.armance_root, ctx.cfg)
        rag_md = format_rag_status_markdown(status)
        read_set = effective_read_set(ctx.armance_root, ctx.session.metadata)
        if read_set:
            rag_md += "\n\n" + t("library.read_header") + "\n"
            for name in sorted(read_set):
                rag_md += t("library.read_line", name=name) + "\n"
    except Exception as exc:
        logger.exception("library-status intercept failed")
        rag_md = t("system.error", body=t("rag_status.failed", error=str(exc)))
    return reply + f"\n\n{rag_md}"
