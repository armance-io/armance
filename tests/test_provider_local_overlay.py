"""LOT C — project-local provider overlay (ADR 0003, §3.3).

A `.armance/config.yaml` in the project folder can ADD instances and EXTEND
allowlists (union), merged over the global config. Secrets are never taken
from the local overlay — API keys stay in `.env`.
"""
from __future__ import annotations

from armance.config import Config, ProviderConfig, merge_provider_overlay


# ---- pure merge --------------------------------------------------------------

def test_overlay_adds_new_instance():
    cfg = Config(providers=[ProviderConfig(name="custom-openai")])
    merge_provider_overlay(cfg, [{"name": "custom-openai:lab", "base_url": "https://lab/v1"}])
    assert cfg.provider("custom-openai:lab").base_url == "https://lab/v1"


def test_overlay_extends_allowlist_union():
    cfg = Config(providers=[ProviderConfig(name="custom-openai:lab", models=["g1"])])
    merge_provider_overlay(cfg, [{"name": "custom-openai:lab", "models": ["g1", "local-x"]}])
    # Union, order-preserving, no dup.
    assert cfg.provider("custom-openai:lab").models == ["g1", "local-x"]


def test_overlay_never_takes_api_key():
    cfg = Config(providers=[ProviderConfig(name="custom-openai:lab")])
    merge_provider_overlay(cfg, [{"name": "custom-openai:lab", "api_key": "leaked"}])
    assert cfg.provider("custom-openai:lab").api_key is None


def test_overlay_new_instance_ignores_api_key():
    cfg = Config(providers=[])
    merge_provider_overlay(cfg, [{"name": "custom-openai:lab", "api_key": "leaked", "models": ["m"]}])
    inst = cfg.provider("custom-openai:lab")
    assert inst.api_key is None
    assert inst.models == ["m"]


def test_overlay_skips_malformed_entries():
    cfg = Config(providers=[ProviderConfig(name="custom-openai")])
    merge_provider_overlay(cfg, ["not-a-dict", {}, {"name": "bad-type:x"}])
    # Original untouched; the invalid-type instance was skipped.
    assert [p.name for p in cfg.providers] == ["custom-openai"]


# ---- through load_config -----------------------------------------------------

def test_load_config_applies_local_overlay(tmp_path, monkeypatch):
    import armance.config as config_mod
    from armance import paths

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(cfg_dir))
    (cfg_dir / "config.yaml").write_text(
        "providers:\n  - name: custom-openai:lab\n    models: [global-a]\n",
        encoding="utf-8",
    )

    project = tmp_path / "proj"
    (project / ".armance").mkdir(parents=True)
    (project / ".armance" / "config.yaml").write_text(
        "providers:\n"
        "  - name: custom-openai:lab\n"
        "    models: [global-a, local-b]\n"
        "  - name: custom-openai:prod\n"
        "    base_url: https://prod/v1\n",
        encoding="utf-8",
    )

    cfg = config_mod.load_config(local_dir=project)
    lab = cfg.provider("custom-openai:lab")
    assert lab.models == ["global-a", "local-b"]  # union extended locally
    assert cfg.provider("custom-openai:prod").base_url == "https://prod/v1"


def test_load_config_no_local_file_is_noop(tmp_path, monkeypatch):
    import armance.config as config_mod
    from armance import paths

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setenv(paths.CONFIG_DIR_ENV, str(cfg_dir))
    (cfg_dir / "config.yaml").write_text(
        "providers:\n  - name: custom-openai\n", encoding="utf-8"
    )
    cfg = config_mod.load_config(local_dir=tmp_path / "empty-project")
    assert [p.name for p in cfg.providers] == ["custom-openai"]
