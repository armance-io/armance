"""GET /projects/{pid}/sessions/{sid}/library — library status.

Returns the RAG / bibliothèque status for the current session's armance_root.
Delegates to armance.storage.rag_status.get_rag_status.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from armance.platform.user import get_current_user
from armance.storage.library_state import effective_read_set
from armance.storage.rag_status import get_rag_status

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["library"])

_EXT_TO_FORMAT = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".md": "md",
    ".txt": "txt",
    ".text": "txt",
}


@router.get("/library")
async def library_status(
    pid: str,
    sid: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Return indexed + read state of the bibliothèque."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    try:
        status = get_rag_status(ws.ctx.armance_root, ws.ctx.cfg)
    except Exception as exc:
        logger.warning("library_status failed sid=%s: %s", sid, exc)
        status = {}

    try:
        read_set = effective_read_set(
            ws.ctx.armance_root,
            ws.ctx.session.metadata if ws.ctx.session else {},
        )
    except Exception:
        read_set = set()

    db_names: set[str] = {d["name"] for d in status.get("docs_in_db", [])}
    # Per-doc feuillet (chunk) counts from the vector DB, keyed by source name.
    chunks_by_doc: dict[str, int] = {
        d.get("source", ""): int(d.get("chunks", 0))
        for d in status.get("docs_in_db", [])
    }

    docs = []
    total_feuillets = 0
    for d in status.get("docs_on_disk", []):
        name: str = d["name"]
        ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        fmt = _EXT_TO_FORMAT.get(ext, "txt")
        if name in read_set:
            doc_status = "loaded"
        elif name in db_names or d.get("in_db"):
            doc_status = "indexed"
        else:
            doc_status = "pending"
        size_bytes = int(d.get("size_kb", 0) * 1024)
        feuillets = chunks_by_doc.get(name, 0)
        total_feuillets += feuillets
        docs.append({
            "name": name,
            "format": fmt,
            "status": doc_status,
            "size_bytes": size_bytes,
            "feuillets": feuillets,
        })

    return {
        "docs": docs,
        "total_feuillets": total_feuillets,
        "doc_count": len(docs),
        "library": status,
    }
