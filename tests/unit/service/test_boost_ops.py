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


class TestSetBoost:
    def _agent(self, boost=True):
        from armance.core.models.agent import Agent
        kw = dict(name="Lea", domain="history", provider="claude-code", model="claude-haiku-4-5")
        if boost:
            kw.update(boost_provider="claude-code", boost_model="claude-sonnet-4-6")
        return Agent(**kw)

    def test_enable_adds_to_set(self) -> None:
        from armance.service.boost_ops import set_boost
        names: set[str] = set()
        assert set_boost(self._agent(), names, enabled=True) is True
        assert "Lea" in names

    def test_disable_removes_from_set(self) -> None:
        from armance.service.boost_ops import set_boost
        names = {"Lea"}
        assert set_boost(self._agent(), names, enabled=False) is False
        assert "Lea" not in names

    def test_enable_non_boostable_is_noop(self) -> None:
        from armance.service.boost_ops import set_boost
        names: set[str] = set()
        # not boostable → cannot enable, returns False, set unchanged
        assert set_boost(self._agent(boost=False), names, enabled=True) is False
        assert names == set()

    def test_disable_non_boostable_still_clears(self) -> None:
        # defensive: a stale name for a now-non-boostable agent is cleared
        from armance.service.boost_ops import set_boost
        names = {"Lea"}
        assert set_boost(self._agent(boost=False), names, enabled=False) is False
        assert names == set()


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
