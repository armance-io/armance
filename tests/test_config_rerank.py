from __future__ import annotations

import logging

import yaml

from armance import paths
from armance.config import Config, load_config, rerank_active


def test_config_defaults_rerank_off():
    cfg = Config()
    assert cfg.rerank_provider == ""
    assert cfg.rerank_model == ""
    assert cfg.rerank_candidate_k == 20
    assert cfg.rerank_keep_n == 5
    assert rerank_active(cfg) is False


def test_rerank_active_requires_both():
    assert rerank_active(Config(rerank_provider="openrouter")) is False
    assert rerank_active(Config(rerank_model="x")) is False
    assert rerank_active(Config(rerank_provider="openrouter", rerank_model="x")) is True


def test_config_round_trip_with_rerank():
    cfg = Config(rerank_provider="openrouter", rerank_model="cohere/rerank-v3.5",
                 rerank_candidate_k=30, rerank_keep_n=4)
    dumped = cfg.model_dump()
    again = Config(**dumped)
    assert again.rerank_model == "cohere/rerank-v3.5"
    assert again.rerank_candidate_k == 30
    assert again.rerank_keep_n == 4


def test_loader_clamps_candidate_k_below_keep_n(tmp_path, monkeypatch, caplog):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.yaml"
    cfg_file.write_text(yaml.safe_dump({
        "default_provider": "openrouter",
        "rerank_provider": "openrouter",
        "rerank_model": "cohere/rerank-v3.5",
        "rerank_candidate_k": 3,
        "rerank_keep_n": 5,
    }), encoding="utf-8")
    monkeypatch.setattr(paths, "global_config_path", lambda: cfg_file)
    monkeypatch.setattr(paths, "global_env_path", lambda: cfg_dir / ".env")
    with caplog.at_level(logging.WARNING):
        cfg = load_config()
    assert cfg.rerank_candidate_k == 5  # clamped up to keep_n
    assert any("rerank" in r.message.lower() for r in caplog.records)
