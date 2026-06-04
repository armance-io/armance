from __future__ import annotations

from pathlib import Path


class TestBoostedModelFor:
    def _agent(self, boost=False):
        from armance.core.models.agent import Agent
        kw = dict(name="Sara", domain="strategy", provider="openrouter", model="base/model")
        if boost:
            kw.update(boost_provider="anthropic", boost_model="claude-opus-4-5")
        return Agent(**kw)

    def test_base_when_not_boosted(self) -> None:
        from armance.service.boost_ops import boosted_model_for
        a = self._agent(boost=True)
        assert boosted_model_for(a, boosted_names=set()) == ("openrouter", "base/model")

    def test_boost_when_active(self) -> None:
        from armance.service.boost_ops import boosted_model_for
        a = self._agent(boost=True)
        assert boosted_model_for(a, boosted_names={"Sara"}) == ("anthropic", "claude-opus-4-5")

    def test_boost_active_but_not_boostable_uses_base(self) -> None:
        from armance.service.boost_ops import boosted_model_for
        a = self._agent(boost=False)
        assert boosted_model_for(a, boosted_names={"Sara"}) == ("openrouter", "base/model")


class TestSessionBoostState:
    def test_boosted_agents_round_trips(self, tmp_path: Path) -> None:
        from armance.service.session import SessionState, load_state, save_state
        st = SessionState.new()
        st.boosted_agents.add("Sara")
        save_state(tmp_path, st)

        loaded = load_state(tmp_path, st.id)
        assert "Sara" in loaded.boosted_agents
        assert loaded.boosted_agents == {"Sara"}

    def test_boosted_agents_defaults_empty(self) -> None:
        from armance.service.session import SessionState
        st = SessionState.new()
        assert st.boosted_agents == set()
