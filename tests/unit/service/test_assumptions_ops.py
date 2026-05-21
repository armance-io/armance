from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.service.assumptions_ops import (
    compile_and_persist,
    split_exec_summary,
)
from armance.service.workflow_runs import create_run


def test_split_exec_summary_empty():
    assert split_exec_summary("") == ""


def test_split_exec_summary_no_separator():
    assert split_exec_summary("just text").strip() == "just text"


def test_split_exec_summary_with_separator():
    content = "Summary line one\nSummary line two\n---\nDetailed register..."
    assert split_exec_summary(content) == "Summary line one\nSummary line two"


@pytest.mark.asyncio
async def test_compile_and_persist_writes_file(tmp_path: Path):
    artefact = create_run(tmp_path, "wf")
    results = {"s1": MagicMock(output="output one"), "s2": MagicMock(output="output two")}

    ctx = MagicMock()
    ctx.armance_root = tmp_path
    ctx.cfg = MagicMock()

    mock_judge = MagicMock()
    mock_judge.compile_assumptions = AsyncMock(return_value="summary\n---\nregister")

    with patch("armance.service.assumptions_ops.JudgeAgent", return_value=mock_judge):
        content = await compile_and_persist(artefact, results, ctx)

    assert content == "summary\n---\nregister"
    assert artefact.assumptions_path().exists()
    assert "register" in artefact.assumptions_path().read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_compile_and_persist_swallows_failure(tmp_path: Path):
    artefact = create_run(tmp_path, "wf")
    results = {"s1": MagicMock(output="x")}

    ctx = MagicMock()
    ctx.armance_root = tmp_path
    ctx.cfg = MagicMock()

    mock_judge = MagicMock()
    mock_judge.compile_assumptions = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("armance.service.assumptions_ops.JudgeAgent", return_value=mock_judge):
        content = await compile_and_persist(artefact, results, ctx)

    assert content == ""
    assert not artefact.assumptions_path().exists()


@pytest.mark.asyncio
async def test_compile_and_persist_skips_write_on_empty(tmp_path: Path):
    artefact = create_run(tmp_path, "wf")
    results = {"s1": MagicMock(output="x")}

    ctx = MagicMock()
    ctx.armance_root = tmp_path
    ctx.cfg = MagicMock()

    mock_judge = MagicMock()
    mock_judge.compile_assumptions = AsyncMock(return_value="")

    with patch("armance.service.assumptions_ops.JudgeAgent", return_value=mock_judge):
        content = await compile_and_persist(artefact, results, ctx)

    assert content == ""
    assert not artefact.assumptions_path().exists()
