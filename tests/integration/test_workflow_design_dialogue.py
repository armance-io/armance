"""DesignWorkflowSkill — stateless YAML parser/validator/writer.

Spec: docs/spec/21_workflow_design.md (rewritten 2026-05-17: Kim LLM
holds the dialogue and emits a YAML block; the skill validates + writes.)
"""
from __future__ import annotations

from armance.core.models.workflow import load_workflow
from armance.service.skills.design_workflow import DesignWorkflowSkill


class _FakeAgent:
    def __init__(self, name: str, domain: str) -> None:
        self.name = name
        self.domain = domain


_ROSTER = [_FakeAgent("Aisha", "historian"), _FakeAgent("Lars", "historian")]


def test_skill_has_expected_attributes() -> None:
    assert DesignWorkflowSkill.slash == "/workflow design"
    assert any("construis" in p for p in DesignWorkflowSkill.nl_patterns)
    assert DesignWorkflowSkill.triggered_by == "user"


def test_valid_yaml_block_writes_workflow(tmp_path) -> None:
    skill = DesignWorkflowSkill(armance_root=tmp_path, config=None, agents=_ROSTER)
    kim_reply = (
        "Voici le workflow proposé.\n\n"
        "```yaml\n"
        "name: dossier-historique\n"
        "strategy: approfondie\n"
        "steps:\n"
        "  - id: propose\n"
        "    kind: task\n"
        "    role: historian\n"
        "    depends_on: []\n"
        "  - id: judge\n"
        "    kind: judge\n"
        "    role: mona\n"
        "    depends_on: [propose]\n"
        "```\n"
    )
    reply = skill.run(args=kim_reply)
    assert "created" in reply.lower() or "créé" in reply.lower()
    workflows_dir = tmp_path / ".armance" / "workflows"
    yaml_files = list(workflows_dir.glob("*.yaml"))
    assert yaml_files
    wf = load_workflow(yaml_files[0])
    assert wf.name == "dossier-historique"
    assert len(wf.steps) == 2
    assert wf.steps[0].domain == "historian"
    assert wf.steps[1].domain == "mona"


def test_no_yaml_block_returns_error(tmp_path) -> None:
    skill = DesignWorkflowSkill(armance_root=tmp_path, config=None, agents=_ROSTER)
    reply = skill.run(args="Voici un workflow sympa mais sans YAML.")
    assert "yaml" in reply.lower() or "⚠" in reply


def test_invalid_kind_rejected(tmp_path) -> None:
    skill = DesignWorkflowSkill(armance_root=tmp_path, config=None, agents=_ROSTER)
    reply = skill.run(args=(
        "```yaml\n"
        "name: bad\n"
        "steps:\n"
        "  - id: foo\n"
        "    kind: not-a-kind\n"
        "    role: historian\n"
        "```\n"
    ))
    assert "invalide" in reply.lower() or "⚠" in reply


def test_step_without_domain_rejected(tmp_path) -> None:
    skill = DesignWorkflowSkill(armance_root=tmp_path, config=None, agents=_ROSTER)
    reply = skill.run(args=(
        "```yaml\n"
        "name: missing-domain\n"
        "steps:\n"
        "  - id: foo\n"
        "    kind: task\n"
        "    depends_on: []\n"
        "```\n"
    ))
    assert "role" in reply.lower() or "domain" in reply.lower()


def test_domain_not_in_roster_rejected(tmp_path) -> None:
    skill = DesignWorkflowSkill(armance_root=tmp_path, config=None, agents=_ROSTER)
    reply = skill.run(args=(
        "```yaml\n"
        "name: bad-domain\n"
        "steps:\n"
        "  - id: foo\n"
        "    kind: task\n"
        "    role: rocket-scientist\n"
        "    depends_on: []\n"
        "```\n"
    ))
    low = reply.lower()
    assert "rocket" in low or "roster" in low or "correspond" in low


def test_mona_serge_domains_accepted_without_roster_entry(tmp_path) -> None:
    skill = DesignWorkflowSkill(armance_root=tmp_path, config=None, agents=_ROSTER)
    reply = skill.run(args=(
        "```yaml\n"
        "name: with-staff\n"
        "steps:\n"
        "  - id: propose\n"
        "    kind: task\n"
        "    role: historian\n"
        "    depends_on: []\n"
        "  - id: critique\n"
        "    kind: critique\n"
        "    role: serge\n"
        "    depends_on: [propose]\n"
        "  - id: judge\n"
        "    kind: judge\n"
        "    role: mona\n"
        "    depends_on: [critique]\n"
        "```\n"
    ))
    assert "created" in reply.lower() or "créé" in reply.lower()


def test_existing_workflow_is_archived(tmp_path) -> None:
    workflows_dir = tmp_path / ".armance" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    existing = workflows_dir / "dossier-historique.yaml"
    existing.write_text("# version: 1\nname: dossier-historique\nsteps: []\n")

    skill = DesignWorkflowSkill(armance_root=tmp_path, config=None, agents=_ROSTER)
    skill.run(args=(
        "```yaml\n"
        "name: dossier-historique\n"
        "steps:\n"
        "  - id: foo\n"
        "    kind: task\n"
        "    role: historian\n"
        "    depends_on: []\n"
        "```\n"
    ))
    archived = list((workflows_dir / ".archive").glob("dossier-historique_v1_*.yaml"))
    assert archived


def test_bare_yaml_with_orphan_closing_fence_parses(tmp_path) -> None:
    r"""Weak LLMs sometimes emit `yaml\n...\n```\n` — bare body with no
    opening fence but a trailing one. Falls back to bare-YAML extraction
    and strips stray fence lines, otherwise the parser errored with
    'racine non-objet' / ScannerError."""
    skill = DesignWorkflowSkill(armance_root=tmp_path, config=None, agents=_ROSTER)
    kim_reply = (
        "yaml\n"
        "name: dossier-historique\n"
        "strategy: approfondie\n"
        "steps:\n"
        "  - id: propose\n"
        "    kind: task\n"
        "    role: historian\n"
        "    depends_on: []\n"
        "  - id: judge\n"
        "    kind: judge\n"
        "    role: mona\n"
        "    depends_on: [propose]\n"
        "```\n"
    )
    reply = skill.run(args=kim_reply)
    assert "racine non-objet" not in reply
    assert "yaml invalide" not in reply.lower() and "invalid yaml" not in reply.lower()
    yaml_files = list((tmp_path / ".armance" / "workflows").glob("*.yaml"))
    assert yaml_files, f"workflow not saved; reply={reply!r}"
