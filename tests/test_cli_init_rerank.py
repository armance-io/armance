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


def test_ask_rerank_skips_providers_without_rerank(monkeypatch):
    # claude-code / gemini clients have no rerank endpoint — never ask.
    def _boom(*a, **k):
        raise AssertionError("must not prompt")

    monkeypatch.setattr(cli.questionary, "text", _boom)
    for prov in ("claude-code", "gemini"):
        assert cli._ask_rerank(prov, "emb-model", [prov], [], language="en") == ("", "")


def test_ask_rerank_provider_decoupled_from_embedding(monkeypatch):
    # Embedding on gemini, but custom-openai is selected too → rerank can
    # still run there. The provider select must default sanely and the
    # returned provider must be the chosen one, not the embedding one.
    class _Sel:
        def ask(self):
            return "custom-openai"

    class _Txt:
        def ask(self):
            return "bge-reranker-v2-m3"

    captured: dict = {}

    def _select(prompt, choices, default, **k):
        captured["choices"] = choices
        captured["default"] = default
        return _Sel()

    monkeypatch.setattr(cli.questionary, "select", _select)
    monkeypatch.setattr(cli.questionary, "text", lambda *a, **k: _Txt())
    out = cli._ask_rerank(
        "gemini", "emb-model",
        ["gemini", "openrouter", "custom-openai"], [], language="en",
    )
    assert out == ("custom-openai", "bge-reranker-v2-m3")
    # gemini/claude-code never appear as rerank choices; default falls back
    # to the first eligible provider since the embedding one is ineligible.
    assert captured["choices"] == ["openrouter", "custom-openai"]
    assert captured["default"] == "openrouter"


def test_ask_rerank_single_eligible_provider_no_select(monkeypatch):
    # One eligible provider → no select prompt, provider taken directly.
    def _boom(*a, **k):
        raise AssertionError("must not prompt select")

    class _Txt:
        def ask(self):
            return "rerank-model"

    monkeypatch.setattr(cli.questionary, "select", _boom)
    monkeypatch.setattr(cli.questionary, "text", lambda *a, **k: _Txt())
    out = cli._ask_rerank(
        "claude-code", "emb-model",
        ["claude-code", "custom-openai"], [], language="en",
    )
    assert out == ("custom-openai", "rerank-model")


def test_ask_rerank_openrouter_prints_proxy_hint(monkeypatch, capsys):
    class _Q:
        def ask(self):
            return ""

    monkeypatch.setattr(cli.questionary, "text", lambda *a, **k: _Q())
    cli._ask_rerank("openrouter", "emb-model", ["openrouter"], [], language="en")
    assert "/rerank" in capsys.readouterr().out   # honest proxy hint shown
