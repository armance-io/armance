"""D.0 — handler for the `[EXECUTE:/workflow-stop:<name>]` tag.

When Kim emits the tag in her reply, this module:
  1. Strips the tag from the reply (so the user never sees it).
  2. Resolves the workflow name to its active run_id via the
     supplied registry (typically `LoopContext.background_runs`).
  3. Calls `executor.cancel(run_id)` — best-effort, no raise on
     unknown name or already-finished run.

The handler is intentionally generic: it takes the executor and the
name→run mapping as arguments so it can be exercised from a unit test
without standing up the full workflow runtime.

Spec: web-d-pipeline.md § D.A + D.0
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_STOP_RE = re.compile(r"\[EXECUTE:/workflow-stop:([\w.-]+)\]")


async def handle_workflow_stop_tag(
    reply: str,
    *,
    executor: Any,
    name_to_run: dict[str, str],
) -> tuple[str, list[str]]:
    """Strip every workflow-stop tag from *reply* and cancel matching runs.

    Returns ``(cleaned_reply, cancelled_run_ids)``.
    """
    matches = list(_STOP_RE.finditer(reply))
    if not matches:
        return reply, []

    cleaned = _STOP_RE.sub("", reply).strip()
    cancelled: list[str] = []
    for m in matches:
        workflow_name = m.group(1)
        run_id = name_to_run.get(workflow_name)
        if run_id is None:
            logger.warning(
                "workflow-stop for '%s' has no active run — ignoring",
                workflow_name,
            )
            continue
        try:
            ok = await executor.cancel(run_id)
        except Exception:
            logger.exception("executor.cancel(%s) failed", run_id)
            continue
        if ok:
            cancelled.append(run_id)
        else:
            logger.info("run '%s' was already finished — nothing to cancel", run_id)
    return cleaned, cancelled
