"""Pre-run health staffing report (degraded gate, W9).

`_role_staffing(wf, ctx)` classifies each required specialist role:
- *staffable* — at least one healthy agent on the roster;
- *sick* — agents exist but none is healthy.
Roles with no agents at all belong to neither list (the runner's absence
path handles them per step). The caller only blocks the run when there
are sick roles and nothing staffable at all.
"""
from __future__ import annotations



from armance.core.models.agent import Agent
from armance.service.handlers import _role_staffing


class _FakeStep:
    def __init__(self, role: str) -> None:
        self.role = role


class _FakeWf:
    def __init__(self, roles: list[str]) -> None:
        self.steps = [_FakeStep(r) for r in roles]


class _FakeCtx:
    def __init__(self, agents):
        self.agents = agents


def _make_agent(name: str, role: str, *, health: str | None = None) -> Agent:
    return Agent(
        name=name, role=role, persona="x",
        provider="openrouter", model="x", system_prompt="x",
        last_health=health,
    )


def test_all_healthy_roster_is_staffable() -> None:
    wf = _FakeWf(["historian", "mona"])
    ctx = _FakeCtx([_make_agent("Aisha", "historian", health="ok")])
    staffable, sick, labels = _role_staffing(wf, ctx)
    assert staffable == ["historian"]
    assert sick == []
    assert labels == []


def test_fully_sick_role_is_flagged_with_agent_labels() -> None:
    wf = _FakeWf(["historian"])
    ctx = _FakeCtx([_make_agent("Elise", "historian", health="error:429")])
    staffable, sick, labels = _role_staffing(wf, ctx)
    assert staffable == []
    assert sick == ["historian"]
    assert labels and "Elise" in labels[0] and "429" in labels[0]


def test_sick_agent_with_healthy_peer_does_not_sicken_the_role() -> None:
    """runtime2 regression: Nora error:400 + Marc ok on `securite` must
    leave the role staffable — the run must not be blocked."""
    wf = _FakeWf(["securite"])
    ctx = _FakeCtx([
        _make_agent("Nora", "securite", health="error:400"),
        _make_agent("Marc", "securite", health="ok"),
    ])
    staffable, sick, labels = _role_staffing(wf, ctx)
    assert staffable == ["securite"]
    assert sick == []


def test_ignores_agents_not_used_by_workflow() -> None:
    wf = _FakeWf(["historian"])
    ctx = _FakeCtx([
        _make_agent("Theo", "historian", health="ok"),
        _make_agent("Logi", "logistician", health="error:auth"),
    ])
    staffable, sick, labels = _role_staffing(wf, ctx)
    assert staffable == ["historian"]
    assert sick == []


def test_staff_domains_excluded_from_health_check() -> None:
    """`mona` / `serge` are staff — resolved at runtime, not from the
    roster — so the pre-run staffing report skips them."""
    wf = _FakeWf(["mona", "serge"])
    ctx = _FakeCtx([])
    assert _role_staffing(wf, ctx) == ([], [], [])


def test_missing_role_is_neither_staffable_nor_sick() -> None:
    """No agent at all for a required role: not a block reason — the
    runner marks those steps absent one by one."""
    wf = _FakeWf(["historian"])
    ctx = _FakeCtx([])
    assert _role_staffing(wf, ctx) == ([], [], [])


def test_agent_with_no_health_record_is_treated_as_healthy() -> None:
    """Never-probed agents are treated as healthy (innocent until proven
    bad). Malik's probe runs at recruit time; legacy agents from before
    this feature won't have a last_health field."""
    wf = _FakeWf(["historian"])
    ctx = _FakeCtx([_make_agent("Old", "historian", health=None)])
    staffable, sick, labels = _role_staffing(wf, ctx)
    assert staffable == ["historian"]
    assert sick == []
