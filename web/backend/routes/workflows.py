"""Workflow routes (D.1–D.5).

GET    /workflows                                    list workflows
GET    /workflows/{name}                              YAML + graph layout
POST   /workflows/{name}/run                          launch (body: mode, depth)
POST   /workflows/{name}/stop                         interrupt (body: confirm)

Spec: web-d-pipeline.md
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from armance.platform.user import get_current_user

from backend.deps import get_app_state
from backend.state import AppState

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
