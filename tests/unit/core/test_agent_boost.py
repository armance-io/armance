from __future__ import annotations


class TestAgentBoost:
    def _agent(self, **kw):
        from armance.core.models.agent import Agent
        base = dict(name="Sara", domain="strategy", provider="openrouter",
                    model="anthropic/claude-3.5-sonnet")
        base.update(kw)
        return Agent(**base)

    def test_boost_fields_default_none(self) -> None:
        a = self._agent()
        assert a.boost_provider is None and a.boost_model is None

    def test_is_boostable(self) -> None:
        a = self._agent(boost_provider="openrouter", boost_model="anthropic/claude-opus-4-5")
        assert a.is_boostable is True
        assert self._agent().is_boostable is False

    def test_effective_boost_returns_boost_pair(self) -> None:
        a = self._agent(boost_provider="anthropic", boost_model="claude-opus-4-5")
        assert a.effective_boost() == ("anthropic", "claude-opus-4-5")

    def test_effective_boost_falls_back_to_base_provider(self) -> None:
        # boost_model set, boost_provider omitted → inherit base provider
        a = self._agent(boost_model="anthropic/claude-opus-4-5")
        assert a.effective_boost() == ("openrouter", "anthropic/claude-opus-4-5")

    def test_effective_boost_none_when_not_boostable(self) -> None:
        assert self._agent().effective_boost() is None

    def test_boost_fields_survive_markdown_roundtrip(self) -> None:
        # Serializer is generic (model_dump -> yaml; model_validate on load),
        # so new fields ride along — assert that explicitly via round-trip.
        a = self._agent(boost_provider="anthropic", boost_model="claude-opus-4-5")
        text = a.to_markdown()
        back = type(a).from_frontmatter(text)
        assert back.boost_provider == "anthropic"
        assert back.boost_model == "claude-opus-4-5"
