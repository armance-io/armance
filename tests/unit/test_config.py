"""Tests for armance.config.

Clean break (grandma launcher): config / secrets / base agents are GLOBAL
(resolved via ``armance.paths``, redirected to a tmp dir by the autouse
``isolate_global_config`` fixture in conftest). Per-folder data still lives
under ``<folder>/.armance`` (``ensure_armance_tree``).
"""
from __future__ import annotations

from pathlib import Path

from armance import paths
from armance.config import (
    Config,
    ProviderConfig,
    ensure_armance_tree,
    ensure_global_setup,
    load_config,
    save_config,
    write_env,
)


def test_ensure_armance_tree(tmp_path: Path) -> None:
    ensure_armance_tree(tmp_path)
    for sub in ("docs", "reports", "context", "agents", "workflows", "judge", "sessions"):
        assert (tmp_path / ".armance" / sub).is_dir()


def test_ensure_global_setup_installs_base_agents(isolate_global_config: Path) -> None:
    """Base agents install into the GLOBAL agents dir, with config substituted."""
    cfg = Config(
        providers=[ProviderConfig(name="gemini", api_key="abc", base_url="https://gemini.com")],
        default_provider="gemini",
        default_model="gemini-2.0-flash",
    )

    ensure_global_setup(cfg)

    sys_ctx_path = paths.global_agents_dir() / "system-context.md"
    assert sys_ctx_path.exists()
    content = sys_ctx_path.read_text(encoding="utf-8")
    assert "provider: gemini" in content
    assert "model: gemini-2.0-flash" in content
    assert "openai/gpt-4o-mini" not in content

    # A user-customised (non-placeholder) agent is preserved on re-run.
    custom_sys_hr = paths.global_agents_dir() / "system-hr.md"
    custom_sys_hr.write_text(
        "provider: anthropic\nmodel: claude-3-5-sonnet\nsystem_prompt: custom\n",
        encoding="utf-8",
    )
    ensure_global_setup(cfg)
    hr_content = custom_sys_hr.read_text(encoding="utf-8")
    assert "claude-3-5-sonnet" in hr_content
    assert "gemini-2.0-flash" not in hr_content

    # A still-placeholder agent IS upgraded.
    custom_sys_hr.write_text(
        "provider: openrouter\nmodel: openai/gpt-4o-mini\nsystem_prompt: placeholder\n",
        encoding="utf-8",
    )
    ensure_global_setup(cfg)
    upgraded = custom_sys_hr.read_text(encoding="utf-8")
    assert "provider: gemini" in upgraded
    assert "model: gemini-2.0-flash" in upgraded
    assert "openai/gpt-4o-mini" not in upgraded


def test_save_strips_api_keys() -> None:
    cfg = Config(
        providers=[ProviderConfig(name="openrouter", api_key="secret", base_url="https://x")],
        default_provider="openrouter",
        default_model="m",
    )
    yaml_path = save_config(cfg)
    raw = yaml_path.read_text(encoding="utf-8")
    assert "secret" not in raw
    assert "openrouter" in raw
    assert "https://x" in raw


def test_write_env_format() -> None:
    providers = [
        ProviderConfig(name="openrouter", api_key="k1", base_url="https://x"),
        ProviderConfig(name="claude-code"),
    ]
    env_path = write_env(providers)
    contents = env_path.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=k1" in contents
    assert "OPENROUTER_BASE_URL=https://x" in contents
    assert "CLAUDE_CODE" not in contents  # no api_key set


def test_round_trip_with_env_override(monkeypatch) -> None:
    cfg = Config(
        providers=[ProviderConfig(name="openrouter", base_url="https://x")],
        default_provider="openrouter",
        default_model="m",
    )
    save_config(cfg)
    write_env([ProviderConfig(name="openrouter", api_key="from-env-file")])

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    loaded = load_config()
    assert loaded.providers[0].api_key == "from-env-file"

    monkeypatch.setenv("OPENROUTER_API_KEY", "from-os-env")
    loaded2 = load_config()
    assert loaded2.providers[0].api_key == "from-os-env"


def test_default_provider_always_listed(isolate_global_config: Path, monkeypatch) -> None:
    """A default_provider missing from providers[] is auto-added on load."""
    monkeypatch.delenv("CLAUDE_CODE_API_KEY", raising=False)
    paths.global_config_path().write_text(
        "default_provider: claude-code\nproviders: []\n", encoding="utf-8"
    )

    cfg = load_config()

    names = [p.name for p in cfg.providers]
    assert "claude-code" in names
    assert cfg.provider("claude-code").name == "claude-code"


def test_default_provider_gets_env_overlay(isolate_global_config: Path, monkeypatch) -> None:
    """The auto-added default provider still receives its env api_key/base_url."""
    paths.global_config_path().write_text(
        "default_provider: custom-openai\nproviders: []\n", encoding="utf-8"
    )
    monkeypatch.setenv("CUSTOM_OPENAI_API_KEY", "k-123")
    monkeypatch.setenv("CUSTOM_OPENAI_BASE_URL", "http://localhost:11434/v1")

    cfg = load_config()
    p = cfg.provider("custom-openai")
    assert p.api_key == "k-123"
    assert p.base_url == "http://localhost:11434/v1"
