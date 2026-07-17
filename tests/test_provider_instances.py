"""LOT A — named provider instances (ADR 0003, design D2).

A provider is a *type*; an instance is `type[:label]`. Two `custom-openai:*`
instances must resolve distinct clients (own base_url/api_key), derive the
right env key, and count as the SAME model family (both OpenAI-compatible).
Back-compat: the 4 bare base names and legacy `.md` `provider: custom-openai`
keep working unchanged.
"""
from __future__ import annotations

import pytest

from armance.config import (
    BASE_PROVIDER_TYPES,
    Config,
    ProviderConfig,
    _env_base_url_for,
    _env_key_for,
    provider_label_of,
    provider_type_of,
)


# ---- type / label derivation -------------------------------------------------

def test_base_names_have_empty_label_and_self_type():
    for base in BASE_PROVIDER_TYPES:
        assert provider_type_of(base) == base
        assert provider_label_of(base) == ""


def test_labelled_instance_splits_type_and_label():
    assert provider_type_of("custom-openai:lab") == "custom-openai"
    assert provider_label_of("custom-openai:lab") == "lab"


def test_provider_config_properties():
    p = ProviderConfig(name="custom-openai:prod", base_url="https://prod/v1")
    assert p.provider_type == "custom-openai"
    assert p.provider_label == "prod"
    assert p.base_url == "https://prod/v1"


def test_bad_provider_type_is_rejected():
    with pytest.raises(ValueError):
        ProviderConfig(name="totally-unknown:lab")


# ---- env key derivation ------------------------------------------------------

def test_env_key_default_unchanged_backcompat():
    # Piège: without care, two instances share the key. The default keeps the
    # historical CUSTOM_OPENAI_API_KEY.
    assert _env_key_for("custom-openai") == "CUSTOM_OPENAI_API_KEY"
    assert _env_base_url_for("custom-openai") == "CUSTOM_OPENAI_BASE_URL"


def test_env_key_labelled_instance():
    assert _env_key_for("custom-openai:lab") == "CUSTOM_OPENAI_LAB_API_KEY"
    assert _env_base_url_for("custom-openai:lab") == "CUSTOM_OPENAI_LAB_BASE_URL"


# ---- Config.provider by full instance name -----------------------------------

def test_config_provider_lookup_by_full_instance_name():
    cfg = Config(
        providers=[
            ProviderConfig(name="custom-openai", base_url="https://default/v1"),
            ProviderConfig(name="custom-openai:lab", base_url="https://lab/v1"),
        ]
    )
    assert cfg.provider("custom-openai").base_url == "https://default/v1"
    assert cfg.provider("custom-openai:lab").base_url == "https://lab/v1"
    with pytest.raises(KeyError):
        cfg.provider("custom-openai:missing")


# ---- factory resolves by type, uses instance config --------------------------

def test_get_client_resolves_by_type_with_instance_config():
    from armance.core.protocols.llm import get_client

    cfg = Config(
        providers=[
            ProviderConfig(name="custom-openai:lab", base_url="https://lab/v1", api_key="k-lab"),
            ProviderConfig(name="custom-openai:prod", base_url="https://prod/v1", api_key="k-prod"),
        ]
    )
    lab = get_client("custom-openai:lab", cfg)
    prod = get_client("custom-openai:prod", cfg)
    # Distinct clients, each carrying its own endpoint + key (the instance
    # ProviderConfig, not the type's).
    assert lab is not prod
    assert lab.base_url == "https://lab/v1"
    assert prod.base_url == "https://prod/v1"
    assert lab._provider.api_key == "k-lab"
    assert prod._provider.api_key == "k-prod"
    assert lab._provider.name == "custom-openai:lab"


def test_get_client_base_provider_still_works():
    from armance.core.protocols.llm import get_client

    cfg = Config(providers=[ProviderConfig(name="custom-openai", base_url="https://gw/v1")])
    client = get_client("custom-openai", cfg)
    assert client.base_url == "https://gw/v1"


# ---- model_family resolves by type (two instances = same family) -------------

def test_model_family_two_instances_same_type_same_family():
    from armance.service.workflow_crucible import model_family

    fam_lab = model_family("custom-openai:lab", "qwen3-72b")
    fam_prod = model_family("custom-openai:prod", "qwen3-72b")
    assert fam_lab == fam_prod  # both qwen — NOT two distinct families


def test_model_family_labelled_claude_code_still_anthropic():
    from armance.service.workflow_crucible import model_family

    assert model_family("claude-code:eu", "claude-sonnet-4-6") == "anthropic"
    assert model_family("gemini:eu", "gemini-2.5-flash") == "google"


def test_available_families_two_custom_instances_is_one_family():
    from armance.service.workflow_crucible import available_model_families

    class _A:
        def __init__(self, provider, model):
            self.provider = provider
            self.model = model

    roster = [_A("custom-openai:lab", "gpt-4o"), _A("custom-openai:prod", "gpt-4o")]
    assert available_model_families(roster) == {"openai"}


# ---- env overlay derives per-instance keys -----------------------------------

def test_load_config_overlays_per_instance_env(tmp_path, monkeypatch):
    import armance.config as config_mod
    from armance import paths

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(cfg_dir))
    (cfg_dir / "config.yaml").write_text(
        "providers:\n"
        "  - name: custom-openai\n"
        "  - name: custom-openai:lab\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CUSTOM_OPENAI_API_KEY", "default-key")
    monkeypatch.setenv("CUSTOM_OPENAI_LAB_API_KEY", "lab-key")
    monkeypatch.setenv("CUSTOM_OPENAI_LAB_BASE_URL", "https://lab/v1")

    cfg = config_mod.load_config()
    assert cfg.provider("custom-openai").api_key == "default-key"
    assert cfg.provider("custom-openai:lab").api_key == "lab-key"
    assert cfg.provider("custom-openai:lab").base_url == "https://lab/v1"
