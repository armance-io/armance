"""Admin stats route — GET /projects/{pid}/admin/stats.

Per-agent tokens_in/tokens_out/cost_usd/msg_count/avg_latency_ms + global.
Cached for 30s per (pid).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from armance.platform.user import get_current_user
from armance.service.stats import compute_stats
from armance.web.backend.deps import get_app_state, resolve_root_or_404
from armance.web.backend.state import AppState

router = APIRouter()

# pid -> (computed_at, result)
_stats_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_TTL = 30.0


def _read_log_records(logs_dir: Path) -> list[dict]:
    """Read all JSON records from *-llm_exchanges.jsonl files."""
    if not logs_dir.exists():
        return []
    records: list[dict] = []
    for log_file in sorted(logs_dir.glob("*.jsonl")):
        try:
            text = log_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return records


@router.get("/projects/{pid}/admin/stats")
async def get_stats(
    pid: str,
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    now = time.monotonic()
    cached = _stats_cache.get(pid)
    if cached is not None and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    logs_dir = resolve_root_or_404(app_state, pid) / "logs"
    records = _read_log_records(logs_dir)
    result = compute_stats(records)

    _stats_cache[pid] = (now, result)
    return result
