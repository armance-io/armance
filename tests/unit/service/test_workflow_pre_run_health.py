"""Pre-run health-check: workflow refuses to start if any required agent
is known-unhealthy on disk."""
from __future__ import annotations



from armance.core.models.agent import Agent
from armance.service.handlers import _collect_unhealthy_agents


class _FakeStep:
    def __init__(self, role: str) -> None:
        self.role = role
        self.domain = role


class _FakeWf:
    def __init__(self, roles: list[str]) -> None:
        self.steps = [_FakeStep(r) for r in roles]


class _FakeCtx:
    def __init__(self, agents):
        self.agents = agents


def _make_agent(name: str, role: str, *, health: str | None = None) -> Agent:
    return Agent(
        name=name, domain=role, role=role, persona="x",
        provider="openrouter", model="x", system_prompt="x",
        last_health=health,
    )


def test_returns_empty_when_all_healthy() -> None:
    wf = _FakeWf(["historian", "mona"])
    ctx = _FakeCtx([_make_agent("Aisha", "historian", health="ok")])
    assert _collect_unhealthy_agents(wf, ctx) == []


def test_flags_agent_with_error_status() -> None:
    wf = _FakeWf(["historian"])
    ctx = _FakeCtx([_make_agent("Elise", "historian", health="error:429")])
    bad = _collect_unhealthy_agents(wf, ctx)
    assert bad and "Elise" in bad[0]
    assert "429" in bad[0]


def test_ignores_agents_not_used_by_workflow() -> None:
    wf = _FakeWf(["historian"])
    ctx = _FakeCtx([
        _make_agent("Theo", "historian", health="ok"),
        _make_agent("Logi", "logistician", health="error:auth"),
    ])
    assert _collect_unhealthy_agents(wf, ctx) == []


def test_staff_domains_excluded_from_health_check() -> None:
    """`mona` / `serge` are staff — resolved at runtime, not from the
    roster — so the pre-run health check skips them."""
    wf = _FakeWf(["mona", "serge"])
    ctx = _FakeCtx([])
    assert _collect_unhealthy_agents(wf, ctx) == []


def test_agent_with_no_health_record_is_not_flagged() -> None:
    """Never-probed agents are treated as healthy (innocent until proven
    bad). Malik's probe runs at recruit time; legacy agents from before
    this feature won't have a last_health field."""
    wf = _FakeWf(["historian"])
    ctx = _FakeCtx([_make_agent("Old", "historian", health=None)])
    assert _collect_unhealthy_agents(wf, ctx) == []
