"""Admin routes — /projects/{pid}/admin/...

EI.7: GET /projects/{pid}/admin/footprint?group_by=agent|day|month|session
  Returns environmental footprint rollup with a 30s cache.
"""
from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from armance.platform.user import get_current_user
from armance.service.equivalences import humanise
from armance.service.footprint_ops import footprint_stats
from armance.web.backend.deps import get_app_state
from armance.web.backend.state import AppState

router = APIRouter()

# (pid, group_by) -> (computed_at, result)
_footprint_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_CACHE_TTL = 30.0


@router.get("/projects/{pid}/admin/footprint")
async def get_footprint(
    pid: str,
    group_by: Annotated[str, Query()] = "agent",
    _user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    """Return environmental footprint rollup for the project.

    ``group_by`` selects which dimension is emphasised in the response
    (all dimensions are always computed; the param controls which is at
    the top level for convenience).  Valid values: agent, day, month, session.
    """
    cache_key = (pid, group_by)
    now = time.monotonic()
    cached = _footprint_cache.get(cache_key)
    if cached is not None and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    logs_dir = app_state.armance_root / "logs"
    stats = footprint_stats(logs_dir, project_id=pid)

    # Derive the project total (midpoint) by summing the per-agent buckets,
    # then translate it into ADEME human-scale equivalences for the browser.
    total_gco2e = sum(b.get("gco2e", 0.0) for b in stats["by_agent"].values())
    total_water = sum(b.get("water_ml", 0.0) for b in stats["by_agent"].values())
    eq = humanise(gco2e=total_gco2e, water_ml=total_water)

    result: dict[str, Any] = {
        "by_agent": stats["by_agent"],
        "by_day": stats["by_day"],
        "by_month": stats["by_month"],
        "by_session": stats["by_session"],
        "dominant_zone": stats["dominant_zone"],
        "equiv": {
            "phone_charges": eq.phone_charges,
            "car_km": eq.car_km,
            "water_glasses": eq.water_glasses,
        },
    }

    _footprint_cache[cache_key] = (now, result)
    return result
