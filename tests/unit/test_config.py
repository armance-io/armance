"""Tests for armance.config."""
from __future__ import annotations

from pathlib import Path

from armance.config import (
    Config,
    ProviderConfig,
    ensure_armance_tree,
    load_config,
    save_config,
    write_env,
)


def test_ensure_armance_tree(tmp_path: Path) -> None:
    ensure_armance_tree(tmp_path)
    for sub in ("docs", "reports", "context", "agents", "workflows", "judge", "sessions"):
        assert (tmp_path / ".armance" / sub).is_dir()


def test_ensure_armance_tree_overrides(tmp_path: Path) -> None:
    # Setup mock config
    cfg = Config(
        providers=[ProviderConfig(name="gemini", api_key="abc", base_url="https://gemini.com")],
        default_provider="gemini",
        default_model="gemini-2.0-flash",
    )
    
    # 1. Run tree initialization with config
    ensure_armance_tree(tmp_path, config=cfg)
    
    # Verify built-in agents (like system-context.md) got modified
    sys_ctx_path = tmp_path / ".armance" / "agents" / "system-context.md"
    assert sys_ctx_path.exists()
    content = sys_ctx_path.read_text(encoding="utf-8")
    assert "provider: gemini" in content
    assert "model: gemini-2.0-flash" in content
    assert "openai/gpt-4o-mini" not in content

    # 2. Test that existing user-edited/customized agents (non gpt-4o-mini) are NOT overwritten
    custom_sys_hr = tmp_path / ".armance" / "agents" / "system-hr.md"
    custom_sys_hr.write_text("provider: anthropic\nmodel: claude-3-5-sonnet\nsystem_prompt: custom\n", encoding="utf-8")
    
    ensure_armance_tree(tmp_path, config=cfg)
    
    hr_content = custom_sys_hr.read_text(encoding="utf-8")
    assert "claude-3-5-sonnet" in hr_content  # Should be preserved!
    assert "gemini-2.0-flash" not in hr_content  # Should NOT be overwritten!

    # 3. Test that existing default placeholder agents (still gpt-4o-mini) ARE upgraded
    placeholder_sys_hr = tmp_path / ".armance" / "agents" / "system-hr.md"
    placeholder_sys_hr.write_text("provider: openrouter\nmodel: openai/gpt-4o-mini\nsystem_prompt: placeholder\n", encoding="utf-8")
    
    ensure_armance_tree(tmp_path, config=cfg)
    
    hr_content_upgraded = placeholder_sys_hr.read_text(encoding="utf-8")
    assert "provider: gemini" in hr_content_upgraded
    assert "model: gemini-2.0-flash" in hr_content_upgraded
    assert "openai/gpt-4o-mini" not in hr_content_upgraded


def test_save_strips_api_keys(tmp_path: Path) -> None:
    cfg = Config(
        providers=[ProviderConfig(name="openrouter", api_key="secret", base_url="https://x")],
        default_provider="openrouter",
        default_model="m",
    )
    yaml_path = save_config(tmp_path, cfg)
    raw = yaml_path.read_text(encoding="utf-8")
    assert "secret" not in raw
    assert "openrouter" in raw
    assert "https://x" in raw


def test_write_env_format(tmp_path: Path) -> None:
    providers = [
        ProviderConfig(name="openrouter", api_key="k1", base_url="https://x"),
        ProviderConfig(name="claude-code"),
    ]
    env_path = write_env(tmp_path, providers)
    contents = env_path.read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=k1" in contents
    assert "OPENROUTER_BASE_URL=https://x" in contents
    assert "CLAUDE_CODE" not in contents  # no api_key set


def test_round_trip_with_env_override(tmp_path: Path, monkeypatch) -> None:
    cfg = Config(
        providers=[ProviderConfig(name="openrouter", base_url="https://x")],
        default_provider="openrouter",
        default_model="m",
    )
    save_config(tmp_path, cfg)
    write_env(tmp_path, [ProviderConfig(name="openrouter", api_key="from-env-file")])

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    loaded = load_config(tmp_path)
    assert loaded.providers[0].api_key == "from-env-file"

    monkeypatch.setenv("OPENROUTER_API_KEY", "from-os-env")
    loaded2 = load_config(tmp_path)
    assert loaded2.providers[0].api_key == "from-os-env"



def test_default_provider_always_listed(tmp_path: Path, monkeypatch) -> None:
    """A default_provider missing from providers[] is auto-added on load.

    Regression: a config with `default_provider: claude-code` but an empty
    `providers` list crashed agent calls with
    `KeyError: provider not configured: claude-code` because
    `Config.provider()` only looked at the list. load_config now guarantees
    the default provider is present (and gets its env overlay).
    """
    monkeypatch.delenv("CLAUDE_CODE_API_KEY", raising=False)
    (tmp_path / ".armance").mkdir()
    (tmp_path / ".armance" / "config.yaml").write_text(
        "default_provider: claude-code\nproviders: []\n", encoding="utf-8"
    )

    cfg = load_config(tmp_path)

    names = [p.name for p in cfg.providers]
    assert "claude-code" in names
    # And .provider() resolves it without raising.
    assert cfg.provider("claude-code").name == "claude-code"


def test_default_provider_gets_env_overlay(tmp_path: Path, monkeypatch) -> None:
    """The auto-added default provider still receives its env api_key/base_url."""
    (tmp_path / ".armance").mkdir()
    (tmp_path / ".armance" / "config.yaml").write_text(
        "default_provider: custom-openai\nproviders: []\n", encoding="utf-8"
    )
    monkeypatch.setenv("CUSTOM_OPENAI_API_KEY", "k-123")
    monkeypatch.setenv("CUSTOM_OPENAI_BASE_URL", "http://localhost:11434/v1")

    cfg = load_config(tmp_path)
    p = cfg.provider("custom-openai")
    assert p.api_key == "k-123"
    assert p.base_url == "http://localhost:11434/v1"
