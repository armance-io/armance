"""Admin logs routes — GET /projects/{pid}/admin/logs + PATCH log-level."""
from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from armance.platform.user import get_current_user
from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

router = APIRouter()

_VALID_LEVELS = {"INFO", "DEBUG", "WARN", "WARNING", "ERROR"}


def _read_all_lines(logs_dir: Any) -> list[dict]:
    """Read every JSON line from all *-llm_exchanges.jsonl files."""
    if not logs_dir.exists():
        return []
    lines: list[dict] = []
    for log_file in sorted(logs_dir.glob("*.jsonl")):
        try:
            text = log_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                lines.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return lines


@router.get("/projects/{pid}/admin/logs")
async def get_logs(
    pid: str,
    agent: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    cursor: Annotated[str | None, Query()] = None,
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    logs_dir = app_state.armance_root / "logs"
    all_lines = _read_all_lines(logs_dir)
    all_lines.reverse()

    if agent:
        filtered = [ln for ln in all_lines if ln.get("agent") == agent]
    else:
        filtered = all_lines

    total = len(filtered)

    offset = 0
    if cursor is not None:
        try:
            offset = int(cursor)
        except ValueError:
            offset = 0

    page = filtered[offset : offset + limit]
    next_offset = offset + len(page)
    next_cursor: str | None = str(next_offset) if next_offset < total else None

    return {"lines": page, "total": total, "cursor": next_cursor}


@router.patch("/projects/{pid}/admin/log-level")
async def set_log_level(
    pid: str,
    body: dict[str, Any],
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    level = str(body.get("level", "")).upper()
    if level not in _VALID_LEVELS:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_level", "valid": sorted(_VALID_LEVELS)},
        )
    numeric = getattr(logging, level, logging.INFO)
    logging.getLogger().setLevel(numeric)
    return {"level": level}
