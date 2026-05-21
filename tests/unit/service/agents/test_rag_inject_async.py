"""inject_rag_section must be a coroutine: it is called from inside the
TUI's running event loop and (soon) FastAPI's, so the previous
asyncio.run()-in-a-thread workaround would crash there.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from armance.service.agents._rag_inject import inject_rag_section


def test_inject_rag_section_is_coroutine():
    assert inspect.iscoroutinefunction(inject_rag_section), (
        "inject_rag_section must be async — FastAPI's loop is already running"
    )


@pytest.mark.asyncio
async def test_inject_rag_section_empty_query(tmp_path: Path):
    assert await inject_rag_section(tmp_path, "") == ""
    assert await inject_rag_section(tmp_path, "   ") == ""


@pytest.mark.asyncio
async def test_inject_rag_section_no_embedding_config(tmp_path: Path):
    # No config => no embedding => empty string
    assert await inject_rag_section(tmp_path, "hello") == ""

    class _Cfg:
        embedding_provider = ""
        embedding_model = ""

    assert await inject_rag_section(tmp_path, "hello", config=_Cfg()) == ""


@pytest.mark.asyncio
async def test_inject_rag_section_runs_inside_running_loop(tmp_path: Path):
    # If the impl ever reintroduces asyncio.run() this would raise
    # `RuntimeError: asyncio.run() cannot be called from a running event loop`.
    result = await inject_rag_section(tmp_path, "anything")
    assert isinstance(result, str)
