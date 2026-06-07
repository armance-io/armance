"""Multi-project root resolution + session isolation (grandma launcher).

The server resolves a project's data root from the ``{pid}`` path param. pid
``default`` keeps the boot root (single-project + power-user ``armance web
<folder>`` stay unchanged); a registry pid resolves to that project's folder;
an unknown pid is a 404. Sessions created under one project must not leak into
another's listing.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from armance.service import launcher_registry as reg
from armance.web.backend.state import AppState


def test_default_pid_keeps_boot_root(tmp_path: Path) -> None:
    boot = tmp_path / "boot" / ".armance"
    boot.mkdir(parents=True)
    state = AppState(armance_root=boot)
    assert state.resolve_root("default") == boot
    assert state.resolve_root("") == boot


def test_registry_pid_resolves_to_project(isolate_global_config: Path, tmp_path: Path) -> None:
    boot = tmp_path / "boot" / ".armance"
    boot.mkdir(parents=True)
    proj = tmp_path / "other"
    proj.mkdir()
    reg.bump_project(proj)
    pid = reg.list_projects()[0]["id"]

    state = AppState(armance_root=boot)
    assert state.resolve_root(pid) == proj.resolve() / ".armance"


def test_unknown_pid_returns_none(tmp_path: Path) -> None:
    boot = tmp_path / "boot" / ".armance"
    boot.mkdir(parents=True)
    state = AppState(armance_root=boot)
    assert state.resolve_root("bogus-pid-deadbeef") is None


@pytest.mark.asyncio
async def test_sessions_isolated_across_projects(
    client: AsyncClient, isolate_global_config: Path, tmp_path: Path
) -> None:
    """A session created under project A does not appear in project B's list."""
    # Two real project folders, each with the global config already seeded.
    proj_a = tmp_path / "A"
    (proj_a / ".armance").mkdir(parents=True)
    proj_b = tmp_path / "B"
    (proj_b / ".armance").mkdir(parents=True)
    reg.bump_project(proj_a)
    reg.bump_project(proj_b)
    items = {p["name"]: p["id"] for p in reg.list_projects()}
    pid_a, pid_b = items["A"], items["B"]

    await client.post(f"/projects/{pid_a}/sessions")

    resp_b = await client.get(f"/projects/{pid_b}/sessions")
    assert resp_b.status_code == 200
    assert resp_b.json() == [] or resp_b.json().get("sessions") == []
