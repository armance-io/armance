"""Tests for `armance init` command."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from armance import cli, paths


class StubPrompt:
    def __init__(self, value: Any) -> None:
        self._value = value

    def ask(self) -> Any:
        return self._value


# Fake embedding fetch: returns one model so the autocomplete is shown
_FAKE_EMBED_MODELS = [("[openrouter]  openai/text-embedding-test  🆓", "openrouter", "openai/text-embedding-test")]


def test_cmd_init_writes_config_env_and_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = iter(
        [
            "English",                                                  # language picker (first)
            ["openrouter"],                                             # checkbox providers
            "sk-test",                                                  # password api_key
            "",                                                         # base_url default kept
            "openrouter",                                               # default provider
            "model-a",                                                  # default model
            "free-first",                                               # budget effort
            # embedding autocomplete: compact label format
            "openai/text-embedding-test  [openrouter]  🆓",
            "FRA · 44.2 gCO2e/kWh",                                     # carbon zone picker
        ]
    )

    def fake_factory(*_a: Any, **_kw: Any) -> StubPrompt:
        return StubPrompt(next(answers))

    monkeypatch.setattr(cli.questionary, "checkbox", fake_factory)
    monkeypatch.setattr(cli.questionary, "password", fake_factory)
    monkeypatch.setattr(cli.questionary, "text", fake_factory)
    monkeypatch.setattr(cli.questionary, "select", fake_factory)
    monkeypatch.setattr(cli.questionary, "autocomplete", fake_factory)
    monkeypatch.setattr(cli, "_fetch_embedding_models", lambda *_a, **_kw: _FAKE_EMBED_MODELS)

    rc = cli.cmd_init(tmp_path)
    assert rc == 0

    # Clean break: config + secrets are GLOBAL; only the data tree is local.
    assert paths.global_config_path().exists()
    local = tmp_path / ".armance"
    for sub in ("docs", "reports", "context", "agents", "workflows", "judge", "sessions"):
        assert (local / sub).is_dir()

    env = paths.global_env_path().read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=sk-test" in env

    yaml_text = paths.global_config_path().read_text(encoding="utf-8")
    assert "sk-test" not in yaml_text
    assert "budget_effort: free-first" in yaml_text
    # The chosen carbon zone is persisted under the footprint config.
    assert "electricity_mix_zone: FRA" in yaml_text


def test_cmd_init_aborts_when_no_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli.questionary, "select", lambda *a, **k: StubPrompt("English"))
    monkeypatch.setattr(cli.questionary, "checkbox", lambda *a, **k: StubPrompt([]))
    rc = cli.cmd_init(tmp_path)
    assert rc == 1
    assert not paths.global_config_path().exists()


def test_cmd_init_gemini_writes_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = iter(
        [
            "English",                           # language picker (first)
            ["gemini"],                          # checkbox providers
            "sk-gemini-key",                     # password api_key
            "",                                  # base_url default kept
            "gemini",                            # default provider
            "gemini-1.5-pro",                    # default model
            "low",                               # budget effort
            "none",                              # skip embedding (autocomplete skip_label, EN)
            "WOR · 473.0 gCO2e/kWh",             # carbon zone picker (world average)
        ]
    )

    def fake_factory(*_a: Any, **_kw: Any) -> StubPrompt:
        return StubPrompt(next(answers))

    monkeypatch.setattr(cli.questionary, "checkbox", fake_factory)
    monkeypatch.setattr(cli.questionary, "password", fake_factory)
    monkeypatch.setattr(cli.questionary, "text", fake_factory)
    monkeypatch.setattr(cli.questionary, "select", fake_factory)
    monkeypatch.setattr(cli.questionary, "autocomplete", fake_factory)
    monkeypatch.setattr(cli, "_fetch_embedding_models", lambda *_a, **_kw: _FAKE_EMBED_MODELS)

    rc = cli.cmd_init(tmp_path)
    assert rc == 0

    env = paths.global_env_path().read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=sk-gemini-key" in env

    yaml_text = paths.global_config_path().read_text(encoding="utf-8")
    assert "budget_effort: low" in yaml_text
    assert "gemini" in yaml_text
