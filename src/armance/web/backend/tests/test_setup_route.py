"""Tests for setup routes (Epic E.1, E.3)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from pathlib import Path


@pytest.fixture()
def clean_armance_root(armance_root: Path) -> Path:
    """An armance_root directory without any config.yaml."""
    cfg_file = armance_root / "config.yaml"
    if cfg_file.exists():
        cfg_file.unlink()
    env_file = armance_root / ".env"
    if env_file.exists():
        env_file.unlink()
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
    assert resp.json() == {"configured": True, "project_id": "default"}

    # Verify config.yaml was written
    cfg_file = clean_armance_root / "config.yaml"
    assert cfg_file.exists()
    
    # Verify .env was written with key
    env_file = clean_armance_root / ".env"
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
