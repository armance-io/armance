"""Workflow routes (D.1–D.5).

GET    /workflows                                    list workflows
GET    /workflows/{name}                              YAML + graph layout
POST   /workflows/{name}/run                          launch (body: mode, depth)
POST   /workflows/{name}/stop                         interrupt (body: confirm)

Spec: web-d-pipeline.md
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import json
import re
import shutil

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from armance.platform.user import get_current_user
from armance.service.tui_bridge import dispatch_input

from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{pid}/sessions/{sid}", tags=["workflows"])


def _load_workflow_safe(path) -> Any | None:
    """Best-effort load — broken YAML returns None instead of raising."""
    try:
        from armance.core.models.workflow import load_workflow
        return load_workflow(path)
    except Exception as exc:
        logger.debug("workflow %s failed to parse: %s", path.name, exc)
        return None


@router.get("/workflows")
async def list_workflows(
    pid: str,
    sid: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """List every workflow YAML in .armance/workflows/."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    wf_dir = ws.ctx.armance_root / "workflows"
    if not wf_dir.exists():
        return {"workflows": []}

    items: list[dict[str, Any]] = []
    for p in sorted(wf_dir.glob("*.yaml")):
        wf = _load_workflow_safe(p)
        if wf is None:
            continue
        items.append({
            "name": wf.name,
            "scope": getattr(wf, "scope", "") or "",
            "step_count": len(getattr(wf, "steps", []) or []),
        })
    return {"workflows": items}


def _compute_layered_lr(steps) -> dict[str, Any]:
    """Tiny dagre-LR replacement — topological levels → (x, y).

    Each step is placed in a column (its topological level), rows
    within a column are evenly spaced. The frontend's React Flow
    accepts (x, y) directly; nodes carry { id, position, data }.
    Edges follow `depends_on`.
    """
    by_id: dict[str, Any] = {s.id: s for s in steps}
    level: dict[str, int] = {}

    def resolve_level(sid: str) -> int:
        if sid in level:
            return level[sid]
        deps = list(getattr(by_id[sid], "depends_on", []) or [])
        if not deps:
            level[sid] = 0
            return 0
        level[sid] = max(resolve_level(d) for d in deps if d in by_id) + 1
        return level[sid]

    for s in steps:
        resolve_level(s.id)

    cols: dict[int, list[str]] = {}
    for sid, lvl in level.items():
        cols.setdefault(lvl, []).append(sid)

    nodes: list[dict[str, Any]] = []
    COL_W = 240
    ROW_H = 120
    for lvl, ids in cols.items():
        for row, sid in enumerate(sorted(ids)):
            step = by_id[sid]
            nodes.append({
                "id": sid,
                "position": {"x": lvl * COL_W, "y": row * ROW_H},
                "data": {
                    "step_id": sid,
                    "kind": getattr(step, "kind", "task"),
                    "role": getattr(step, "role", None) or getattr(step, "domain", "") or "",
                },
            })

    edges: list[dict[str, str]] = []
    for s in steps:
        for dep in (getattr(s, "depends_on", []) or []):
            edges.append({
                "id": f"{dep}->{s.id}",
                "source": dep,
                "target": s.id,
            })

    return {"nodes": nodes, "edges": edges}


@router.get("/workflows/{name}")
async def get_workflow(
    pid: str,
    sid: str,
    name: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Return the parsed workflow YAML plus a left-to-right graph layout."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    wf_path = ws.ctx.armance_root / "workflows" / f"{name}.yaml"
    if not wf_path.exists():
        raise HTTPException(status_code=404, detail="workflow_not_found")
    wf = _load_workflow_safe(wf_path)
    if wf is None:
        raise HTTPException(status_code=422, detail="workflow_invalid_yaml")

    steps = list(getattr(wf, "steps", []) or [])
    return {
        "name": wf.name,
        "scope": getattr(wf, "scope", "") or "",
        "strategy": getattr(wf, "strategy", "") or "",
        "steps": [
            {
                "id": s.id,
                "kind": getattr(s, "kind", "task"),
                "role": getattr(s, "role", None) or getattr(s, "domain", "") or "",
                "depends_on": list(getattr(s, "depends_on", []) or []),
            }
            for s in steps
        ],
        "graph": _compute_layered_lr(steps),
    }


def _safe_wf(name: str) -> str:
    return re.sub(r"[^\w-]", "_", name)[:64]


def _require_workflow(ws, name: str):
    wf_path = ws.ctx.armance_root / "workflows" / f"{name}.yaml"
    if not wf_path.exists():
        raise HTTPException(status_code=404, detail="workflow_not_found")
    return wf_path


# --- D.4 -----------------------------------------------------------------

class RunIn(BaseModel):
    mode: str = "interactive"


async def _dispatch_run(ws, name: str, mode: str) -> dict[str, Any]:
    """Thin seam — patched in unit tests.  Forwards to Kim via /workflow-run."""
    reply, _agent = await dispatch_input(
        f"/workflow run {name} {mode}",
        ws.ctx,
    )
    # Backend doesn't return a run_id directly; derive from current state.
    safe = _safe_wf(name)
    runs_index = ws.ctx.armance_root / "exports" / safe / "runs.json"
    run_id = ""
    if runs_index.exists():
        try:
            runs = json.loads(runs_index.read_text(encoding="utf-8"))
            if isinstance(runs, list) and runs:
                last = runs[-1]
                if isinstance(last, dict):
                    run_id = str(last.get("run_id", ""))
        except Exception:
            pass
    return {"ack": True, "run_id": run_id, "reply_preview": reply[:200]}


@router.post("/workflows/{name}/run", status_code=202)
async def run_workflow(
    pid: str,
    sid: str,
    name: str,
    body: RunIn,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Launch a workflow run in the background and return immediately.

    The run executes as a detached asyncio task so this request returns at
    once: the run can then pause on HITL checkpoints (resolved by separate
    POST /checkpoint requests) and the frontend tracks progress via
    GET /active-workflow + the run manifest. ``run_id`` is empty here — the
    client discovers it from /active-workflow once the run dir is minted.
    """
    if body.mode not in ("interactive", "autonomous"):
        raise HTTPException(status_code=400, detail="invalid_mode")
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    _require_workflow(ws, name)

    if ws.run_task is not None and not ws.run_task.done():
        raise HTTPException(status_code=409, detail={"error": "run_already_active"})

    async def _runner() -> object:
        try:
            return await _dispatch_run(ws, name, body.mode)
        except Exception:  # noqa: BLE001 — log, never crash the event loop
            logger.exception("workflow run failed sid=%s name=%s", sid, name)
            return {"ack": False}
        finally:
            ws.run_task = None

    ws.run_task = asyncio.create_task(_runner())
    return {"ack": True, "run_id": "", "started": True}


# --- D.5 -----------------------------------------------------------------

class StopIn(BaseModel):
    confirm: bool = False


async def _dispatch_stop(ws, name: str) -> dict[str, Any]:
    """Thin seam — forwards a stop request through Kim's /workflow-stop tag."""
    reply, _agent = await dispatch_input(
        f"/workflow stop {name}",
        ws.ctx,
    )
    return {"cancelled": True, "reply_preview": reply[:200]}


@router.post("/workflows/{name}/stop")
async def stop_workflow(
    pid: str,
    sid: str,
    name: str,
    body: StopIn,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    if not body.confirm:
        raise HTTPException(status_code=409, detail={"error": "confirm_required"})
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    _require_workflow(ws, name)
    return await _dispatch_stop(ws, name)


# --- D.6 -----------------------------------------------------------------

class DeleteRunIn(BaseModel):
    confirm: bool = False


@router.delete("/workflows/{name}/runs/{run_id}")
async def delete_run(
    pid: str,
    sid: str,
    name: str,
    run_id: str,
    body: DeleteRunIn,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    if not body.confirm:
        raise HTTPException(status_code=409, detail={"error": "confirm_required"})
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")
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

    # Active run protection — surfaces if `current_workflow` matches AND
    # the run is the most recent entry of runs.json.
    state_wf = getattr(ws.session.state, "current_workflow", None)
    if state_wf == name:
        runs_index = exports_root / safe / "runs.json"
        if runs_index.exists():
            try:
                runs = json.loads(runs_index.read_text(encoding="utf-8"))
                last = runs[-1] if isinstance(runs, list) and runs else None
                if isinstance(last, dict) and last.get("run_id") == run_id:
                    raise HTTPException(status_code=409, detail="run_is_active")
            except HTTPException:
                raise
            except Exception:
                pass

    shutil.rmtree(run_dir)
    # Update runs.json — drop the entry if present.
    runs_index = exports_root / safe / "runs.json"
    if runs_index.exists():
        try:
            runs = json.loads(runs_index.read_text(encoding="utf-8"))
            if isinstance(runs, list):
                runs = [r for r in runs if not (isinstance(r, dict) and r.get("run_id") == run_id)]
                runs_index.write_text(json.dumps(runs), encoding="utf-8")
        except Exception:
            logger.exception("failed to rewrite runs.json")

    return {"deleted": True}
