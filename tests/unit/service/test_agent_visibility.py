from __future__ import annotations

from armance.core.models.turn import Turn
from armance.service.agent_visibility import visible_turns


def _t(role: str, content: str, agent: str) -> Turn:
    return Turn(role=role, content=content, agent=agent)


def test_specialist_sees_own_and_framing_not_recruitment():
    turns = [
        _t("user", "conference on climate", "system-context"),
        _t("assistant", "what audience?", "system-context"),
        _t("user", "change Samir model to gpt-oss", "system-hr"),
        _t("assistant", "updated", "system-hr"),
        _t("user", "present yourself", "Samir"),
    ]
    out = visible_turns(turns, "Samir")
    contents = [m["content"] for m in out]
    assert "conference on climate" in contents
    assert "present yourself" in contents
    assert "change Samir model to gpt-oss" not in contents
    assert "updated" not in contents
    assert all(set(m.keys()) == {"role", "content"} for m in out)


def test_malik_sees_recruitment_crosstalk():
    turns = [
        _t("user", "recruit a scientist", "system-hr"),
        _t("assistant", "proposed Elena", "system-hr"),
        _t("user", "present yourself", "Samir"),
    ]
    out = visible_turns(turns, "system-hr")
    contents = [m["content"] for m in out]
    assert "recruit a scientist" in contents
    assert "proposed Elena" in contents
    assert "present yourself" not in contents


def test_armance_sees_everything():
    turns = [
        _t("user", "a", "system-context"),
        _t("user", "b", "system-hr"),
        _t("user", "c", "Samir"),
    ]
    out = visible_turns(turns, "system-context")
    assert [m["content"] for m in out] == ["a", "b", "c"]


def test_specialist_path_filter_matches_policy():
    turns = [
        Turn(role="user", content="climate conference", agent="system-context"),
        Turn(role="user", content="change Mateo model", agent="system-hr"),
        Turn(role="user", content="hello Mateo", agent="Mateo"),
    ]
    out = [m["content"] for m in visible_turns(turns, "Mateo")]
    assert "change Mateo model" not in out
    assert "climate conference" in out
    assert "hello Mateo" in out


def test_bare_malik_viewer_sees_recruitment():
    turns = [
        Turn(role="user", content="recruit a scientist", agent="system-hr"),
        Turn(role="user", content="present yourself", agent="Samir"),
    ]
    out = [m["content"] for m in visible_turns(turns, "malik")]
    assert "recruit a scientist" in out
    assert "present yourself" not in out


def test_empty_turns_returns_empty():
    assert visible_turns([], "Samir") == []


def test_orchestrator_excludes_recruitment_and_specialist_dms():
    turns = [
        Turn(role="user", content="framing goal", agent="system-context"),
        Turn(role="user", content="recruit a scientist", agent="system-hr"),
        Turn(role="user", content="hello specialist", agent="Samir"),
        Turn(role="user", content="design a workflow", agent="system-orchestrator"),
    ]
    out = [m["content"] for m in visible_turns(turns, "system-orchestrator")]
    assert "framing goal" in out
    assert "design a workflow" in out
    assert "recruit a scientist" not in out
    assert "hello specialist" not in out
