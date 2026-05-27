"""D.0 — [EXECUTE:/workflow-stop:<name>] tag handling.

Kim is the only role allowed to emit it. Other roles get the tag
stripped by the sandbox scrubber.

When Kim emits the tag and a workflow with that name is running
(tracked in a process-local registry of WorkflowExecutor run handles),
the handler calls executor.cancel() and the manifest gets
status="cancelled" + cancelled_at.

Spec: web-d-pipeline.md § D.A + D.0
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from armance.service.agent_sandbox import scrub_reply


def test_kim_keeps_workflow_stop_tag() -> None:
    reply = "Bien. [EXECUTE:/workflow-stop:dossier-vapp]"
    out = scrub_reply(reply, agent_role="kim")
    assert "[EXECUTE:/workflow-stop:dossier-vapp]" in out


def test_armance_loses_workflow_stop_tag() -> None:
    reply = "[EXECUTE:/workflow-stop:dossier-vapp]"
    out = scrub_reply(reply, agent_role="armance")
    assert "[EXECUTE:/workflow-stop" not in out


def test_malik_loses_workflow_stop_tag() -> None:
    reply = "[EXECUTE:/workflow-stop:dossier-vapp]"
    out = scrub_reply(reply, agent_role="malik")
    assert "[EXECUTE:/workflow-stop" not in out


@pytest.mark.asyncio
async def test_stop_handler_cancels_active_run() -> None:
    """The stop_ops handler resolves the workflow name via the active-run
    registry and calls executor.cancel()."""
    from armance.service.stop_ops import handle_workflow_stop_tag

    executor = MagicMock()
    executor.cancel = AsyncMock(return_value=True)

    registry: dict[str, str] = {"dossier-vapp": "run-1"}
    reply = "Bien. [EXECUTE:/workflow-stop:dossier-vapp]"

    out, cancelled = await handle_workflow_stop_tag(
        reply, executor=executor, name_to_run=registry,
    )
    assert "[EXECUTE:/workflow-stop" not in out
    assert cancelled == ["run-1"]
    executor.cancel.assert_awaited_once_with("run-1")


@pytest.mark.asyncio
async def test_stop_handler_no_active_run_is_noop() -> None:
    from armance.service.stop_ops import handle_workflow_stop_tag

    executor = MagicMock()
    executor.cancel = AsyncMock()
    reply = "[EXECUTE:/workflow-stop:absent-wf]"
    out, cancelled = await handle_workflow_stop_tag(
        reply, executor=executor, name_to_run={},
    )
    assert "[EXECUTE:/workflow-stop" not in out
    assert cancelled == []
    executor.cancel.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_handler_passthrough_no_tag() -> None:
    from armance.service.stop_ops import handle_workflow_stop_tag

    executor = MagicMock()
    executor.cancel = AsyncMock()
    reply = "Nothing to stop here."
    out, cancelled = await handle_workflow_stop_tag(
        reply, executor=executor, name_to_run={"x": "run-x"},
    )
    assert out == reply
    assert cancelled == []
    executor.cancel.assert_not_awaited()
