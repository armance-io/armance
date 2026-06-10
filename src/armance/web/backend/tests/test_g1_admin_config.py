"""G1 — GET /projects/{pid}/admin/config + PATCH /projects/{pid}/admin/config.

Tests:
  - GET returns loaded config dict (no api_key leak).
  - PATCH with a valid field writes config.yaml and returns 200.
  - PATCH with an unknown field returns 422 with field list.
  - PATCH with an invalid value returns 422 with field list.
"""
from __future__ import annotations

import pytest
import yaml
from pathlib import Path
from httpx import AsyncClient


def _write_config(armance_root: Path, data: dict) -> None:
    # Clean break: config is GLOBAL, not under the project's local .armance.
    from armance import paths

    paths.global_config_dir().mkdir(parents=True, exist_ok=True)
    paths.global_config_path().write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.mark.asyncio
async def test_get_config_returns_config(client: AsyncClient, armance_root: Path) -> None:
    _write_config(armance_root, {"language": "fr", "default_model": "some/model"})

    resp = await client.get("/projects/default/admin/config")

    assert resp.status_code == 200
    body = resp.json()
    assert body["language"] == "fr"
    assert body["default_model"] == "some/model"


@pytest.mark.asyncio
async def test_get_config_does_not_leak_api_keys(client: AsyncClient, armance_root: Path) -> None:
    _write_config(armance_root, {
        "providers": [{"name": "openrouter", "api_key": "sk-secret-key"}],
    })

    resp = await client.get("/projects/default/admin/config")

    assert resp.status_code == 200
    body = resp.json()
    for provider in body.get("providers", []):
        assert provider.get("api_key") is None, "api_key must not leak via GET /admin/config"


@pytest.mark.asyncio
async def test_patch_config_valid_field_writes_yaml(client: AsyncClient, armance_root: Path) -> None:
    _write_config(armance_root, {"language": "en", "default_model": "old/model"})

    resp = await client.patch(
        "/projects/default/admin/config",
        json={"default_model": "new/model"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["default_model"] == "new/model"

    from armance import paths
    saved = yaml.safe_load(paths.global_config_path().read_text())
    assert saved["default_model"] == "new/model"


@pytest.mark.asyncio
async def test_patch_config_unknown_field_returns_422(client: AsyncClient, armance_root: Path) -> None:
    _write_config(armance_root, {"language": "en"})

    resp = await client.patch(
        "/projects/default/admin/config",
        json={"bogus_field": "value"},
    )

    assert resp.status_code == 422
    body = resp.json()
    # FastAPI wraps HTTPException detail under "detail"
    fields = body.get("detail", body).get("fields", {})
    assert "bogus_field" in fields


@pytest.mark.asyncio
async def test_patch_config_invalid_value_returns_422(client: AsyncClient, armance_root: Path) -> None:
    _write_config(armance_root, {"language": "en"})

    resp = await client.patch(
        "/projects/default/admin/config",
        json={"language": "zz"},
    )

    assert resp.status_code == 422
    body = resp.json()
    fields = body.get("detail", body).get("fields", {})
    assert "language" in fields
