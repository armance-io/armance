"""Tests for setup routes (Epic E.1, E.3)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from pathlib import Path


@pytest.fixture()
def clean_armance_root(armance_root: Path) -> Path:
    """A project root whose GLOBAL config + .env have been removed.

    Clean break: setup status / init read and write the global config dir, so
    that is what must be cleared to simulate an unconfigured install.
    """
    from armance import paths

    for f in (paths.global_config_path(), paths.global_env_path()):
        if f.exists():
            f.unlink()
    return armance_root


@pytest.mark.asyncio
async def test_setup_status_unconfigured(
    client: AsyncClient,
    clean_armance_root: Path,
) -> None:
    """GET /setup/status returns configured=False when config.yaml is absent."""
    resp = await client.get("/setup/status")
    assert resp.status_code == 200
    assert resp.json() == {
        "configured": False,
        "missing": ["default_provider", "default_model"],
    }


@pytest.mark.asyncio
async def test_setup_status_configured(
    client: AsyncClient,
    armance_root: Path,
) -> None:
    """GET /setup/status returns configured=True when config.yaml exists."""
    resp = await client.get("/setup/status")
    assert resp.status_code == 200
    assert resp.json() == {"configured": True}


@pytest.mark.asyncio
async def test_setup_init_success(
    client: AsyncClient,
    clean_armance_root: Path,
) -> None:
    """POST /setup/init initialises the configuration and environment correctly."""
    resp = await client.post(
        "/setup/init",
        json={
            "provider": "openrouter",
            "api_key": "sk-test-key",
            "model": "openai/gpt-4o-mini",
            "budget": "free-first",
            "language": "en",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["configured"] is True
    assert body["project_id"] == "default"

    # Verify config.yaml + .env were written to the GLOBAL dir (clean break).
    from armance import paths

    # The response surfaces the resolved config dir (discoverability + the
    # write self-check landing point).
    assert body["config_dir"] == str(paths.global_config_dir())
    assert paths.global_config_path().exists()
    env_file = paths.global_env_path()
    assert env_file.exists()
    env_content = env_file.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=sk-test-key" in env_content


@pytest.mark.asyncio
async def test_setup_init_invalid_provider(
    client: AsyncClient,
    clean_armance_root: Path,
) -> None:
    """POST /setup/init fails with 400 for unknown provider."""
    resp = await client.post(
        "/setup/init",
        json={
            "provider": "bogus-provider",
            "model": "openai/gpt-4o-mini",
            "budget": "free-first",
            "language": "en",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "unknown_provider"


@pytest.mark.asyncio
async def test_setup_init_invalid_budget(
    client: AsyncClient,
    clean_armance_root: Path,
) -> None:
    """POST /setup/init fails with 422 for invalid budget effort value."""
    resp = await client.post(
        "/setup/init",
        json={
            "provider": "openrouter",
            "model": "openai/gpt-4o-mini",
            "budget": "bogus-budget",
            "language": "en",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_setup_init_persists_electricity_zone(client: AsyncClient) -> None:
    """The wizard's grid-zone choice lands in footprint.electricity_mix_zone."""
    resp = await client.post("/setup/init", json={
        "provider": "openrouter",
        "api_key": "sk-test",
        "model": "openai/gpt-4o-mini",
        "budget": "optimised",
        "language": "fr",
        "electricity_zone": "FRA",
    })
    assert resp.status_code == 201
    from armance.config import load_config
    cfg = load_config()
    assert cfg.footprint.electricity_mix_zone == "FRA"
    assert cfg.budget_effort == "optimised"


@pytest.mark.asyncio
async def test_setup_init_rejects_legacy_budget(client: AsyncClient) -> None:
    """Only the two curated postures are accepted at setup time."""
    resp = await client.post("/setup/init", json={
        "provider": "openrouter",
        "model": "openai/gpt-4o-mini",
        "budget": "medium",
        "language": "en",
    })
    assert resp.status_code == 422
