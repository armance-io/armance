"""Tests for armance.service.tui_bridge."""
from __future__ import annotations

from pathlib import Path


from armance.core.models.agent import Agent
from armance.service.tui_bridge import (
    agent_label,
    detect_switch_intent,
    find_agent_by_name,
    find_agents_by_role,
    load_user_agents,
)


def _mk_agent(name: str, role: str = "woodworker", character: str = "balanced") -> Agent:
    return Agent.model_validate({
        "name": name,
        "role": role,
        "character": character,
        "provider": "openrouter",
        "model": "m",
        "system_prompt": "You are a test agent.",
    })


# ---------------------------------------------------------------------------
# agent_label
# ---------------------------------------------------------------------------

def test_agent_label_user_agent():
    """User agent: 'Tom · woodworker'."""
    agents = [_mk_agent("Tom", role="woodworker")]
    label, role = agent_label("Tom", agents)
    assert label == "Tom · woodworker"
    assert role == "agent"


def test_agent_label_system_context():
    """System context persona: 'Armance · weaver'."""
    label, role = agent_label("system-context", [])
    assert label == "Armance · weaver"
    assert role == "agent"


def test_agent_label_system_hr():
    """System HR persona: 'Malik · scout'."""
    label, role = agent_label("system-hr", [])
    assert label == "Malik · scout"
    assert role == "agent"


def test_agent_label_orchestrator():
    """Workflow creator persona: 'Kim · conductor'."""
    label, role = agent_label("system-orchestrator", [])
    assert label == "Kim · conductor"
    assert role == "agent"


def test_agent_label_judge():
    """Judge persona: 'Mona · distiller'."""
    label, role = agent_label("system-judge", [])
    assert label == "Mona · distiller"
    assert role == "agent"


def test_agent_label_unknown():
    """Unknown agent name: returns name as-is."""
    label, role = agent_label("ghost", [])
    assert label == "ghost"
    assert role == "agent"


def test_agent_label_no_agent():
    """None agent name: 'agent'."""
    label, role = agent_label(None, [])
    assert label == "agent"
    assert role == "agent"


# ---------------------------------------------------------------------------
# detect_switch_intent
# ---------------------------------------------------------------------------

def test_detect_switch_at_mention():
    assert detect_switch_intent("@Tom please help") == "Tom"


def test_detect_switch_at_mention_only():
    assert detect_switch_intent("@Tom") == "Tom"


def test_detect_switch_nl_french_no_longer_matches():
    # Natural-language verbs are no longer a switch trigger — only `@`.
    assert detect_switch_intent("je veux discuter avec Tom") is None


def test_detect_switch_nl_english_no_longer_matches():
    assert detect_switch_intent("I want to talk to Tom") is None


def test_detect_switch_addressing_someone_in_third_person():
    # "Malik, change Priya's model" used to switch to Priya — must not.
    assert detect_switch_intent("Malik, change Priya's model to sonnet") is None


def test_detect_switch_no_match():
    assert detect_switch_intent("Hi, how are you?") is None


# ---------------------------------------------------------------------------
# find_agent_by_name / find_agents_by_pole
# ---------------------------------------------------------------------------

def test_find_agent_exact_name():
    agents = [_mk_agent("Tom"), _mk_agent("Marie")]
    assert find_agent_by_name(agents, "Tom").name == "Tom"
    assert find_agent_by_name(agents, "tom").name == "Tom"


def test_find_agent_prefix():
    agents = [_mk_agent("tom-audacious"), _mk_agent("marie-prudent")]
    assert find_agent_by_name(agents, "tom").name == "tom-audacious"


def test_find_agent_not_found():
    agents = [_mk_agent("Tom")]
    assert find_agent_by_name(agents, "Marie") is None


def test_find_agents_by_role():
    agents = [
        _mk_agent("Tom", role="woodworker"),
        _mk_agent("Marie", role="woodworker"),
        _mk_agent("Bob", role="electrician"),
    ]
    found = find_agents_by_role(agents, "woodworker")
    assert len(found) == 2
    assert {a.name for a in found} == {"Tom", "Marie"}


def test_find_agents_by_role_case_insensitive():
    agents = [_mk_agent("Tom", role="Woodworker")]
    found = find_agents_by_role(agents, "woodworker")
    assert len(found) == 1


# ---------------------------------------------------------------------------
# load_user_agents
# ---------------------------------------------------------------------------

def test_load_user_agents_skips_system(tmp_path: Path):
    armance = tmp_path / ".armance"
    agents_dir = armance / "agents"
    agents_dir.mkdir(parents=True)

    (agents_dir / "Tom.md").write_text(
        """---
name: Tom
domain: woodworker
role: woodworker
character: balanced
provider: openrouter
model: m
---
Body.
""",
        encoding="utf-8",
    )
    (agents_dir / "system-context.md").write_text(
        """---
name: system-context
domain: system
character: balanced
provider: openrouter
model: m
---
System body.
""",
        encoding="utf-8",
    )

    loaded = load_user_agents(armance)
    assert len(loaded) == 1
    assert loaded[0].name == "Tom"


def test_load_user_agents_empty_dir(tmp_path: Path):
    assert load_user_agents(tmp_path / ".armance") == []
