"""Launcher route tests (grandma launcher, sub-feature 2).

Covers the registry-backed endpoints, the auth gate (a new router must be
covered by the Epic-S middleware without per-route work), and the
security-sensitive ``/browse`` path-traversal rejection at the HTTP layer.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient



@pytest.mark.asyncio
async def test_launcher_lists_projects(client: AsyncClient, tmp_path: Path) -> None:
    proj = tmp_path / "myproj"
    proj.mkdir()
    await client.post("/launcher/open", json={"path": str(proj)})

    resp = await client.get("/launcher")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["projects"]]
    assert "myproj" in names


@pytest.mark.asyncio
async def test_launcher_new_creates_data_tree(client: AsyncClient, tmp_path: Path) -> None:
    proj = tmp_path / "fresh"
    proj.mkdir()
    resp = await client.post("/launcher/new", json={"path": str(proj)})
    assert resp.status_code == 200
    assert (proj / ".armance" / "docs").is_dir()
    # Returns the pid the frontend navigates to (/projects/{pid}).
    body = resp.json()
    assert body["id"]
    assert body["name"] == "fresh"


@pytest.mark.asyncio
async def test_launcher_open_missing_path_404(client: AsyncClient, tmp_path: Path) -> None:
    resp = await client.post("/launcher/open", json={"path": str(tmp_path / "nope")})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_launcher_requires_auth() -> None:
    """A request without the session cookie is rejected by the Epic-S gate.

    Asserts the new router is auto-covered by the fail-closed middleware (no
    per-route Depends needed).
    """
    from armance.web.backend.main import create_app
    from armance.web.backend.state import AppState

    app = create_app()
    # Mirror the serving path: lifespan sets app_state (the gate no-ops when it
    # is None). With state present but no cookie, the gate must reject.
    app.state.app_state = AppState(armance_root=Path("/tmp"))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:  # no AUTH_COOKIES
        resp = await ac.get("/launcher")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_browse_lists_subdirs(client: AsyncClient, monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    (home / "projects").mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    resp = await client.get("/launcher/browse", params={"path": str(home)})
    assert resp.status_code == 200
    assert [d["name"] for d in resp.json()["dirs"]] == ["projects"]


@pytest.mark.asyncio
async def test_browse_can_leave_home(client: AsyncClient, monkeypatch, tmp_path: Path) -> None:
    """Local single user: the picker can navigate above/outside home."""
    home = tmp_path / "home" / "sub"
    home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    # Navigate to the parent of home — previously rejected, now allowed.
    resp = await client.get("/launcher/browse", params={"path": str(tmp_path)})
    assert resp.status_code == 200
    assert resp.json()["parent"] is not None  # not at the FS anchor


@pytest.mark.asyncio
async def test_browse_nonexistent_rejected(client: AsyncClient, tmp_path: Path) -> None:
    resp = await client.get("/launcher/browse", params={"path": str(tmp_path / "nope")})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_path"


@pytest.mark.asyncio
async def test_mkdir_creates_folder(client: AsyncClient, tmp_path: Path) -> None:
    resp = await client.post(
        "/launcher/mkdir", json={"path": str(tmp_path), "name": "NewProj"}
    )
    assert resp.status_code == 200
    assert (tmp_path / "NewProj").is_dir()
    assert resp.json()["name"] == "NewProj"


@pytest.mark.asyncio
async def test_mkdir_rejects_bad_name(client: AsyncClient, tmp_path: Path) -> None:
    resp = await client.post(
        "/launcher/mkdir", json={"path": str(tmp_path), "name": "../escape"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_filesystem_routes_non_loopback_forbidden(armance_root: Path) -> None:
    """browse / mkdir are loopback-only (403 from a remote IP)."""
    from armance.web.backend.main import create_app
    from armance.web.backend.state import AppState
    from .conftest import AUTH_COOKIES

    app = create_app()
    app.state.app_state = AppState(armance_root=armance_root)
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("8.8.8.8", 0)),
        base_url="http://test",
        cookies=AUTH_COOKIES,
    ) as remote:
        b = await remote.get("/launcher/browse")
        m = await remote.post("/launcher/mkdir", json={"path": "/tmp", "name": "x"})
        o = await remote.post("/launcher/open", json={"path": "/tmp"})
    assert b.status_code == 403
    assert m.status_code == 403
    assert o.status_code == 403
