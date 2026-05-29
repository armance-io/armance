"""Tests for the Ctrl+Q quit gate cache handling.

`MainScreen._quit_with_save_prompt` only touches a handful of attributes,
so we drive it via the unbound method on a lightweight stub. Only the
Textual-specific bits (app.exit, notify, checkpoint handler) are faked;
the cache/L0 side is exercised against a real ContextService at tmp_path.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from armance.client.tui.screens.main import MainScreen
from armance.service.checkpoint import CheckpointResponse
from armance.service.context_service import ContextService


def _make_stub(tmp_path, resp: CheckpointResponse):
    """Build a minimal stub exposing exactly what the method reads."""
    handler = SimpleNamespace(prompt=AsyncMock(return_value=resp))
    stub = SimpleNamespace(
        armance_root=tmp_path,
        _loop_ctx=SimpleNamespace(checkpoint_handler=handler),
        session=SimpleNamespace(save=MagicMock()),
        _quit_in_progress=True,
        app=SimpleNamespace(exit=MagicMock()),
        notify=MagicMock(),
    )
    return stub


def _seed_cache(tmp_path) -> ContextService:
    svc = ContextService(tmp_path)
    svc.cache_append("pending note that must not be lost")
    assert svc.read_cache()  # sanity
    return svc


@pytest.mark.asyncio
async def test_abort_cancels_quit_and_keeps_cache(tmp_path):
    svc = _seed_cache(tmp_path)
    stub = _make_stub(tmp_path, CheckpointResponse(content="", is_abort=True))

    await MainScreen._quit_with_save_prompt(stub)

    # Cache intact, app did NOT exit, re-entry guard reset.
    assert svc.read_cache() == "pending note that must not be lost"
    stub.app.exit.assert_not_called()
    assert stub._quit_in_progress is False


@pytest.mark.asyncio
async def test_yes_saves_cache_and_exits(tmp_path):
    svc = _seed_cache(tmp_path)
    stub = _make_stub(tmp_path, CheckpointResponse(content="yes", is_abort=False))

    await MainScreen._quit_with_save_prompt(stub)

    # Cache folded into a real L0 file, then cleared; app exited.
    assert svc.read_cache() == ""
    assert svc.read_current_l0() is not None
    l0_body = svc.read_l0_body() or ""
    assert "pending note that must not be lost" in l0_body
    stub.session.save.assert_called_once()
    stub.app.exit.assert_called_once_with(0)


@pytest.mark.asyncio
async def test_no_drops_cache_and_exits(tmp_path):
    svc = _seed_cache(tmp_path)
    stub = _make_stub(tmp_path, CheckpointResponse(content="no", is_abort=False))

    await MainScreen._quit_with_save_prompt(stub)

    # Cache dropped, but no L0 written; app exited.
    assert svc.read_cache() == ""
    assert svc.read_current_l0() is None
    stub.app.exit.assert_called_once_with(0)
