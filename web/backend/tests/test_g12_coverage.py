"""G12 — Additional coverage tests to reach ≥ 90% on admin routes and core services.

Covers edge cases not hit by G5-G8 main tests:
  - admin_stats: missing logs dir, invalid JSON line, empty line, OSError, cache hit.
  - admin_logs: invalid JSON line, empty line, OSError during file read, invalid cursor parsing.
  - admin_secrets: client being None, localhost guard.
  - admin_agents: invalid agent name regex match, unknown field, agent not found, agent not on disk, reasoning update.
  - config_ops: validate_config_patch validation error and unknown field error.
  - env_ops: invalid key name, illegal control characters in value, parse_env edge cases, list_secrets with missing .env.
  - stats: compute_stats with empty list, event not response, latency not present.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

from armance.config import Config
from armance.platform.storage import LocalFilesystemStorage
from armance.service.config_ops import validate_config_patch, ConfigValidationError
from armance.service.env_ops import list_secrets, set_secret, delete_secret, EnvKeyError
from armance.service.stats import compute_stats


# ---------------------------------------------------------------------------
# core service/stats unit tests
# ---------------------------------------------------------------------------

def test_service_stats_edge_cases() -> None:
    # 1. Empty records list
    res = compute_stats([])
    assert res["agents"] == {}
    assert res["global"]["msg_count"] == 0

    # 2. Event not response
    res = compute_stats([{"event": "request", "agent": "Armance"}])
    assert res["agents"] == {}

    # 3. Latency not present or None
    records = [
        {"event": "response", "agent": "Kim", "tokens_in": 10, "tokens_out": 20, "cost_usd": 0.01},
        {"event": "response", "agent": "Kim", "tokens_in": 5, "tokens_out": 5, "cost_usd": 0.005, "latency_ms": None},
    ]
    res = compute_stats(records)
    assert "Kim" in res["agents"]
    assert res["agents"]["Kim"]["msg_count"] == 2
    assert res["agents"]["Kim"]["avg_latency_ms"] == 0.0


# ---------------------------------------------------------------------------
# core service/config_ops unit tests
# ---------------------------------------------------------------------------

def test_service_config_validation_errors() -> None:
    current = Config()
    
    # 1. Unknown field patch
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_patch(current, {"not_a_field": 123})
    assert "not_a_field" in exc_info.value.fields
    assert exc_info.value.fields["not_a_field"] == "unknown field"

    # 2. Validation error (invalid language literal)
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_patch(current, {"language": "invalid_lang"})
    assert "language" in exc_info.value.fields


# ---------------------------------------------------------------------------
# core service/env_ops unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_service_env_ops_errors(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(root=tmp_path)
    
    # 1. Invalid key name regex
    with pytest.raises(EnvKeyError):
        await set_secret(storage, "lower_key", "value")
    
    with pytest.raises(EnvKeyError):
        await delete_secret(storage, "lower_key")

    # 2. Illegal control characters
    with pytest.raises(EnvKeyError):
        await set_secret(storage, "VALID_KEY", "value\nwith\nnewlines")

    # 3. list_secrets when .env does not exist
    res = await list_secrets(storage)
    assert res == []

    # 4. delete_secret when .env does not exist
    found = await delete_secret(storage, "VALID_KEY")
    assert found is False

    # 5. parsing .env with comment/blank line edge cases
    await storage.write_text(".env", "# This is a comment\n\nSOME_KEY=some_value\nINVALID LINE WITHOUT EQUAL\n")
    secrets = await list_secrets(storage)
    assert len(secrets) == 1
    assert secrets[0]["name"] == "SOME_KEY"


# ---------------------------------------------------------------------------
# admin_stats route and helper edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stats_missing_logs_dir(client: AsyncClient, armance_root: Path) -> None:
    from backend.routes.admin_stats import _stats_cache
    _stats_cache.clear()

    resp = await client.get("/projects/default/admin/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["agents"] == {}
    assert body["global"]["msg_count"] == 0


@pytest.mark.asyncio
async def test_stats_invalid_json_line(client: AsyncClient, armance_root: Path) -> None:
    from backend.routes.admin_stats import _stats_cache
    _stats_cache.clear()

    logs_dir = armance_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / "llm_exchanges.jsonl").write_text(
        '{"event":"response","agent":"X","tokens_in":10,"tokens_out":5,"cost_usd":0.001,"latency_ms":100}\n'
        "NOT_JSON\n"
        "\n"  # empty line
        '{"event":"response","agent":"X","tokens_in":20,"tokens_out":8,"cost_usd":0.002,"latency_ms":200}\n',
        encoding="utf-8",
    )

    resp = await client.get("/projects/default/admin/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["agents"]["X"]["msg_count"] == 2


@pytest.mark.asyncio
async def test_stats_read_os_error(client: AsyncClient, armance_root: Path) -> None:
    from backend.routes.admin_stats import _stats_cache
    _stats_cache.clear()

    logs_dir = armance_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / "llm_exchanges.jsonl"
    log_file.write_text('{"event":"response","agent":"X"}', encoding="utf-8")

    # Mock Path.read_text to raise OSError to cover except OSError block
    with patch.object(Path, "read_text", side_effect=OSError("Permission denied")):
        resp = await client.get("/projects/default/admin/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agents"] == {}  # reading failed, returned empty records list


@pytest.mark.asyncio
async def test_stats_cache_hit(client: AsyncClient, armance_root: Path) -> None:
    from backend.routes.admin_stats import _stats_cache
    _stats_cache.clear()

    logs_dir = armance_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / "llm_exchanges.jsonl").write_text(
        '{"event":"response","agent":"CacheTest","tokens_in":10}\n', encoding="utf-8"
    )

    resp1 = await client.get("/projects/default/admin/stats")
    assert resp1.status_code == 200
    assert "CacheTest" in resp1.json()["agents"]

    # Mutate log file but expect cached result
    (logs_dir / "llm_exchanges.jsonl").write_text(
        '{"event":"response","agent":"ShouldNotSeeThis","tokens_in":10}\n', encoding="utf-8"
    )

    resp2 = await client.get("/projects/default/admin/stats")
    assert resp2.status_code == 200
    assert "CacheTest" in resp2.json()["agents"]
    assert "ShouldNotSeeThis" not in resp2.json()["agents"]


# ---------------------------------------------------------------------------
# admin_logs edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logs_invalid_json_line(client: AsyncClient, armance_root: Path) -> None:
    logs_dir = armance_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / "llm_exchanges.jsonl").write_text(
        '{"event":"response","agent":"A","timestamp":"2026-01-01T00:00:00"}\n'
        "INVALID\n"
        "\n",
        encoding="utf-8",
    )

    resp = await client.get("/projects/default/admin/logs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_logs_read_os_error(client: AsyncClient, armance_root: Path) -> None:
    logs_dir = armance_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / "llm_exchanges.jsonl").write_text('{"event":"response","agent":"A"}', encoding="utf-8")

    with patch.object(Path, "read_text", side_effect=OSError("Read error")):
        resp = await client.get("/projects/default/admin/logs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_logs_invalid_cursor(client: AsyncClient, armance_root: Path) -> None:
    logs_dir = armance_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / "llm_exchanges.jsonl").write_text('{"event":"response","agent":"A"}\n', encoding="utf-8")

    # Pass an invalid non-integer cursor
    resp = await client.get("/projects/default/admin/logs?cursor=not-an-int")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1


# ---------------------------------------------------------------------------
# admin_secrets edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_secrets_client_none(client: AsyncClient, armance_root: Path) -> None:
    from backend.state import AppState
    from backend.main import create_app
    from httpx import AsyncClient as AC, ASGITransport
    from fastapi import Request
    from unittest.mock import PropertyMock, patch

    app = create_app()
    app.state.app_state = AppState(armance_root=armance_root)

    with patch.object(Request, "client", new_callable=PropertyMock, return_value=None):
        async with AC(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/projects/default/admin/secrets")
            assert resp.status_code == 403
            assert resp.json() == {"error": "secrets_localhost_only"}



# ---------------------------------------------------------------------------
# admin_agents edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_agent_invalid_name(client: AsyncClient, armance_root: Path) -> None:
    from backend.state import WebSession, AppState
    from unittest.mock import MagicMock
    import os
    os.environ["ARMANCE_ROOT"] = str(armance_root.parent)
    from backend.main import create_app
    from httpx import AsyncClient as AC, ASGITransport

    mock_ctx = MagicMock()
    mock_ctx.armance_root = armance_root
    mock_ctx.agents = []
    mock_ctx.ledger = MagicMock()
    mock_ctx.ledger.snapshot.return_value = {}

    ws = WebSession(
        sid="invalid-name-sid",
        project_id="default",
        session=MagicMock(),
        ctx=mock_ctx,
        bus=MagicMock(),
        handler=MagicMock(),
    )
    app = create_app()
    app.state.app_state = AppState(armance_root=armance_root)
    app.state.app_state.put(ws)

    # Regex test with a name that is invalid but doesn't change path segments
    async with AC(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            f"/projects/default/sessions/{ws.sid}/agents/Alice.Bob",
            json={"model": "x"},
        )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "invalid_agent_name"


@pytest.mark.asyncio
async def test_patch_agent_unknown_field(client: AsyncClient, armance_root: Path) -> None:
    from backend.state import WebSession, AppState
    from armance.core.models.agent import Agent
    import os
    os.environ["ARMANCE_ROOT"] = str(armance_root.parent)
    from backend.main import create_app
    from httpx import AsyncClient as AC, ASGITransport

    agents_dir = armance_root / "agents"
    agents_dir.mkdir(exist_ok=True)
    alice = Agent(name="AliceCov", domain="analyst", model="gpt-4o-mini", provider="openrouter")
    (agents_dir / "AliceCov.md").write_text(alice.to_markdown(), encoding="utf-8")

    mock_ctx = MagicMock()
    mock_ctx.armance_root = armance_root
    mock_ctx.agents = [alice]
    mock_ctx.ledger = MagicMock()
    mock_ctx.ledger.snapshot.return_value = {}

    ws = WebSession(
        sid="unknown-field-sid",
        project_id="default",
        session=MagicMock(),
        ctx=mock_ctx,
        bus=MagicMock(),
        handler=MagicMock(),
    )
    app = create_app()
    app.state.app_state = AppState(armance_root=armance_root)
    app.state.app_state.put(ws)

    async with AC(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            f"/projects/default/sessions/{ws.sid}/agents/AliceCov",
            json={"unknown_field": "x"},
        )

    assert resp.status_code == 422
    body = resp.json()
    detail = body.get("detail", body)
    assert detail.get("error") == "unknown_fields"


@pytest.mark.asyncio
async def test_patch_agent_not_found(client: AsyncClient, armance_root: Path) -> None:
    from backend.state import WebSession, AppState
    from backend.main import create_app
    from httpx import AsyncClient as AC, ASGITransport

    mock_ctx = MagicMock()
    mock_ctx.armance_root = armance_root
    mock_ctx.agents = []
    mock_ctx.ledger = MagicMock()
    mock_ctx.ledger.snapshot.return_value = {}

    ws = WebSession(
        sid="not-found-sid",
        project_id="default",
        session=MagicMock(),
        ctx=mock_ctx,
        bus=MagicMock(),
        handler=MagicMock(),
    )
    app = create_app()
    app.state.app_state = AppState(armance_root=armance_root)
    app.state.app_state.put(ws)

    async with AC(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            f"/projects/default/sessions/{ws.sid}/agents/ValidButMissing",
            json={"model": "gpt-4o"},
        )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "agent_not_found"


@pytest.mark.asyncio
async def test_patch_agent_not_on_disk_and_reasoning(client: AsyncClient, armance_root: Path) -> None:
    from backend.state import WebSession, AppState
    from armance.core.models.agent import Agent
    from backend.main import create_app
    from httpx import AsyncClient as AC, ASGITransport

    # Agent is in memory but not on disk
    alice = Agent(name="AliceNotOnDisk", domain="analyst", model="gpt-4o-mini", provider="openrouter", reasoning="effort_low")

    mock_ctx = MagicMock()
    mock_ctx.armance_root = armance_root
    mock_ctx.agents = [alice]
    mock_ctx.ledger = MagicMock()
    mock_ctx.ledger.snapshot.return_value = {}

    ws = WebSession(
        sid="not-on-disk-sid",
        project_id="default",
        session=MagicMock(),
        ctx=mock_ctx,
        bus=MagicMock(),
        handler=MagicMock(),
    )
    app = create_app()
    app.state.app_state = AppState(armance_root=armance_root)
    app.state.app_state.put(ws)

    async with AC(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            f"/projects/default/sessions/{ws.sid}/agents/AliceNotOnDisk",
            json={"reasoning": "effort_high"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "AliceNotOnDisk"
    assert body["reasoning"] == "effort_high"

    # Verify file was written
    from armance.storage.paths import agent_path
    path = agent_path(armance_root, "AliceNotOnDisk")
    assert path.exists()
    on_disk = Agent.load(path)
    assert on_disk.reasoning == "effort_high"
