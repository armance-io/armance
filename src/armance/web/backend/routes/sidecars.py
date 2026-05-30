"""D.7 — GET /workflows/{name}/runs/{run_id}/{arguments|sources}.

Reads Mona's JSON sidecars (D.B + D.C schemas) and returns them as-is.
When the sidecar is absent, returns the empty v1 envelope so the
frontend can render an empty list without special-casing.

Spec: web-d-pipeline.md § D.7
"""
from __future__ import annotations

import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException

from armance.platform.storage import LocalFilesystemStorage
from armance.platform.user import get_current_user

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/projects/{pid}/sessions/{sid}/workflows/{name}",
    tags=["sidecars"],
)


def _safe_wf(name: str) -> str:
    return re.sub(r"[^\w-]", "_", name)[:64]


async def _read_sidecar(ws, name: str, run_id: str, filename: str) -> dict | None:
    if not re.fullmatch(r"[\w.-]+", run_id):
        raise HTTPException(status_code=400, detail="invalid_run_id")
    safe = _safe_wf(name)
    run_dir = ws.ctx.armance_root / "exports" / safe / run_id
    exports_root = ws.ctx.armance_root / "exports"
    try:
        run_dir.resolve().relative_to(exports_root.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_path")
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="run_not_found")

    storage = LocalFilesystemStorage(root=ws.ctx.armance_root)
    rel = f"exports/{safe}/{run_id}/{filename}"
    if not await storage.exists(rel):
        return None
    raw = await storage.read_text(rel)
    try:
        return json.loads(raw)
    except Exception:
        logger.warning("sidecar %s invalid JSON", rel)
        return None


@router.get("/runs/{run_id}/arguments")
async def get_arguments(
    pid: str,
    sid: str,
    name: str,
    run_id: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    payload = await _read_sidecar(ws, name, run_id, "arguments.json")
    if payload is None:
        return {"version": 1, "run_id": run_id, "arguments": []}
    return payload


@router.get("/runs/{run_id}/sources")
async def get_sources(
    pid: str,
    sid: str,
    name: str,
    run_id: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    payload = await _read_sidecar(ws, name, run_id, "sources.json")
    if payload is None:
        return {"version": 1, "sources": []}
    return payload
