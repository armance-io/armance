from __future__ import annotations

from armance import cli


def test_ask_rerank_skips_when_no_embedding():
    # No embedding configured → rerank makes no sense → skip silently.
    assert cli._ask_rerank("", "", ["openrouter"], [], language="en") == ("", "")


def test_ask_rerank_blank_input_returns_empty(monkeypatch):
    class _Q:
        def ask(self):
            return ""

    monkeypatch.setattr(cli.questionary, "text", lambda *a, **k: _Q())
    out = cli._ask_rerank("openrouter", "emb-model", ["openrouter"], [], language="en")
    assert out == ("", "")


def test_ask_rerank_returns_provider_model(monkeypatch):
    class _Q:
        def ask(self):
            return "cohere/rerank-v3.5"

    monkeypatch.setattr(cli.questionary, "text", lambda *a, **k: _Q())
    out = cli._ask_rerank("openrouter", "emb-model", ["openrouter"], [], language="en")
    assert out == ("openrouter", "cohere/rerank-v3.5")
