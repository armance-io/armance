"""Unit tests for library_web_ops.run_library_action — the structured
library action used by the web UI (returns {ok, message, error})."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from armance.service.library_web_ops import run_library_action


def _ctx(tmp_path):
    ctx = MagicMock()
    ctx.armance_root = tmp_path
    ctx.cfg = MagicMock()
    return ctx


@pytest.mark.asyncio
async def test_index_all_ok(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    with patch(
        "armance.storage.ingestion.sync_docs",
        return_value={"indexed": 1, "chunks": 23, "skipped": 0, "deleted": 0},
    ):
        res = await run_library_action("index", None, ctx)
    assert res["ok"] is True
    assert res["error"] is None


@pytest.mark.asyncio
async def test_index_embed_init_failed_surfaces_error(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    with patch(
        "armance.storage.ingestion.sync_docs",
        return_value={"error": "embed_init_failed"},
    ):
        res = await run_library_action("index", None, ctx)
    assert res["ok"] is False
    assert res["error"] == "embed_init_failed"


@pytest.mark.asyncio
async def test_index_missing_file_returns_not_found(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    res = await run_library_action("index", "absent.pdf", ctx)
    assert res["ok"] is False
    assert res["error"] == "not_found"


@pytest.mark.asyncio
async def test_unknown_action(tmp_path) -> None:
    res = await run_library_action("bogus", None, _ctx(tmp_path))
    assert res["ok"] is False
    assert res["error"] == "unknown_action"


@pytest.mark.asyncio
async def test_state_action_delegates_to_dispatch(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    with patch(
        "armance.service.library_web_ops.dispatch",
        new=AsyncMock(return_value="loaded"),
    ) as disp:
        res = await run_library_action("load", "doc.pdf", ctx)
    disp.assert_awaited_once()
    assert res["ok"] is True
    assert res["message"] == "loaded"
