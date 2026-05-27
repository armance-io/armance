"""GET /workflows/{name}/runs/{run_id}/hypotheses — Mona's hypothesis ledger.

Scans every `step-*.md` file in the run directory for Mona's
autonomous-mode markers, in either French or English form:

  **Hypothèse (Mona) :** <text>
  **Hypothesis (Mona):**  <text>

Returns the structured list for the LivePanel HypothesisList component.

Spec: web-c-deliberation.md § C.10
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from armance.platform.storage import LocalFilesystemStorage
from armance.platform.user import get_current_user

from backend.deps import get_app_state
from backend.state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/projects/{pid}/sessions/{sid}/workflows/{name}",
    tags=["hypotheses"],
)

# Match `**Hypothèse (Mona) :** <text…>`  OR
#       `**Hypothesis (Mona):**  <text…>` — capture the trailing text
#       up to the end of the line.
_RE_FR = re.compile(r"\*\*Hypothèse \(Mona\)\s*:\*\*\s*(.+)", re.IGNORECASE)
_RE_EN = re.compile(r"\*\*Hypothesis \(Mona\)\s*:\*\*\s*(.+)", re.IGNORECASE)

# step-<id>.md → capture <id>
_STEP_FILE_RE = re.compile(r"^step-(?P<id>[\w-]+)\.md$")


def _safe_wf_name(name: str) -> str:
    return re.sub(r"[^\w-]", "_", name)[:64]


@router.get("/runs/{run_id}/hypotheses")
async def list_hypotheses(
    pid: str,
    sid: str,
    name: str,
    run_id: str,
    user: str = Depends(get_current_user),
    app_state: AppState = Depends(get_app_state),
) -> dict:
    """Return every Mona hypothesis marker found in the run's step-*.md files."""
    ws = app_state.get(sid)
    if ws is None:
        raise HTTPException(status_code=404, detail="session_not_found")

    safe_wf = _safe_wf_name(name)
    if not re.fullmatch(r"[\w.-]+", run_id):
        raise HTTPException(status_code=400, detail="invalid_run_id")

    run_dir = ws.ctx.armance_root / "exports" / safe_wf / run_id

    # Security: ensure the resolved path doesn't escape `exports`.
    exports_root = ws.ctx.armance_root / "exports"
    try:
        run_dir.resolve().relative_to(exports_root.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_path")

    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="run_not_found")

    storage = LocalFilesystemStorage(root=ws.ctx.armance_root)

    items: list[dict[str, str]] = []
    # Iterate files sorted for deterministic ordering across calls.
    for step_file in sorted(run_dir.glob("step-*.md")):
        m = _STEP_FILE_RE.match(step_file.name)
        if not m:
            continue
        step_id = m.group("id")
        rel_key = f"exports/{safe_wf}/{run_id}/{step_file.name}"
        try:
            content = await storage.read_text(rel_key)
        except FileNotFoundError:
            continue
        for line in content.splitlines():
            fr = _RE_FR.search(line)
            en = _RE_EN.search(line)
            if fr:
                items.append({
                    "step_id": step_id,
                    "text": fr.group(1).strip(),
                    "language": "fr",
                })
            elif en:
                items.append({
                    "step_id": step_id,
                    "text": en.group(1).strip(),
                    "language": "en",
                })

    return {"hypotheses": items}
