"""Registry pid scheme (multi-project server, grandma launcher).

Each project gets a stable slug-based ``id`` (pid) that appears in
``/projects/{pid}`` URLs and resolves back to its folder. pids resolve ONLY via
the registry — a raw pid never builds an arbitrary filesystem path.
"""
from __future__ import annotations

from pathlib import Path


from armance.service import launcher_registry as reg


def test_bump_assigns_stable_pid(isolate_global_config: Path, tmp_path: Path) -> None:
    proj = tmp_path / "Table Basse"
    proj.mkdir()
    reg.bump_project(proj)

    items = reg.list_projects()
    assert items[0]["id"]  # a non-empty slug
    pid = items[0]["id"]

    # Re-bump keeps the same pid (stable across opens).
    reg.bump_project(proj)
    assert reg.list_projects()[0]["id"] == pid


def test_distinct_folders_get_distinct_pids(isolate_global_config: Path, tmp_path: Path) -> None:
    a = tmp_path / "proj"
    a.mkdir()
    b = tmp_path / "sub" / "proj"
    b.mkdir(parents=True)  # same basename
    reg.bump_project(a)
    reg.bump_project(b)
    pids = {p["id"] for p in reg.list_projects()}
    assert len(pids) == 2  # no collision despite identical folder name


def test_path_for_pid_resolves(isolate_global_config: Path, tmp_path: Path) -> None:
    proj = tmp_path / "alpha"
    proj.mkdir()
    reg.bump_project(proj)
    pid = reg.list_projects()[0]["id"]
    assert reg.path_for_pid(pid) == proj.resolve()


def test_path_for_pid_unknown_returns_none(isolate_global_config: Path) -> None:
    assert reg.path_for_pid("does-not-exist") is None
