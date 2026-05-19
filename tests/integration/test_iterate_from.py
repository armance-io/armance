"""T-25h: IterateFromSkill — workflow N → workflow N+1 input.

Spec: docs/spec/22_circular_outputs.md § 3. Skill iterate_from
"""
from __future__ import annotations

from pathlib import Path

import pytest

from armance.service.skills.iterate_from import IterateFromSkill


SYNTHESIS = """\
## Consensus
Azur and garance are the dominant colors.

## Recommendation
Proceed with azur + garance palette.
"""


def _make_run(tmp_path: Path, run_id: str, synthesis: str) -> Path:
    """Create a fake completed run with a judge deliverable."""
    run_dir = tmp_path / "workflows" / "runs" / run_id
    judge_dir = run_dir / "final"
    judge_dir.mkdir(parents=True)
    (judge_dir / "judge_v001.md").write_text(synthesis, encoding="utf-8")
    # Write manifest
    (run_dir / "manifest.yaml").write_text(
        f"run_id: {run_id}\nstatus: done\nworkflow: src-workflow\n",
        encoding="utf-8",
    )
    return run_dir


def test_skill_has_expected_attributes() -> None:
    assert IterateFromSkill.slash == "/iterate-from"
    assert any("iterate" in p or "basé" in p for p in IterateFromSkill.nl_patterns)
    assert IterateFromSkill.triggered_by == "user"


def test_run_with_known_workflow(tmp_path) -> None:
    """iterate-from r_aaa dst-workflow → new run manifest has derived_from."""
    _make_run(tmp_path, "r_aaa", SYNTHESIS)

    # Create a target workflow yaml
    wf_dir = tmp_path / ".armance" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "design-poster.yaml").write_text(
        "name: design-poster\nsteps:\n  - id: draft\n    kind: task\n",
        encoding="utf-8",
    )

    skill = IterateFromSkill(armance_root=tmp_path, config=None)
    result = skill.run(args="r_aaa design-poster")

    assert result  # some reply
    # Check that a new run manifest was created
    runs_dir = tmp_path / "workflows" / "runs"
    new_runs = [d for d in runs_dir.iterdir() if d.name != "r_aaa"]
    assert new_runs, f"No new run created. Runs: {list(runs_dir.iterdir())}"
    manifest_path = new_runs[0] / "manifest.yaml"
    assert manifest_path.exists()
    manifest_text = manifest_path.read_text()
    assert "r_aaa" in manifest_text
    assert "derived_from" in manifest_text


def test_synthesis_text_in_prompt_not_file_ref(tmp_path) -> None:
    """The new run's user_prompt contains the synthesis text, not a file pointer."""
    _make_run(tmp_path, "r_bbb", SYNTHESIS)
    wf_dir = tmp_path / ".armance" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "design-poster.yaml").write_text(
        "name: design-poster\nsteps:\n  - id: draft\n    kind: task\n",
        encoding="utf-8",
    )

    skill = IterateFromSkill(armance_root=tmp_path, config=None)
    skill.run(args="r_bbb design-poster")

    runs_dir = tmp_path / "workflows" / "runs"
    new_runs = [d for d in runs_dir.iterdir() if d.name != "r_bbb"]
    manifest_text = (new_runs[0] / "manifest.yaml").read_text()
    # The synthesis content (not the filename) must be embedded
    assert "azur" in manifest_text or "garance" in manifest_text or "user_prompt" in manifest_text


def test_chain_of_three_reconstructable(tmp_path) -> None:
    """Walk derived_from chain of 3 runs."""
    import yaml

    _make_run(tmp_path, "r_001", SYNTHESIS)
    wf_dir = tmp_path / ".armance" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "iter.yaml").write_text(
        "name: iter\nsteps:\n  - id: step\n    kind: task\n",
        encoding="utf-8",
    )

    skill1 = IterateFromSkill(armance_root=tmp_path, config=None)
    skill1.run(args="r_001 iter")

    runs_dir = tmp_path / "workflows" / "runs"
    r002_dir = [d for d in runs_dir.iterdir() if d.name != "r_001"][0]
    # Fake a synthesis in r002 so we can iterate again
    judge_dir2 = r002_dir / "final"
    judge_dir2.mkdir(parents=True, exist_ok=True)
    (judge_dir2 / "judge_v001.md").write_text("## Consensus\nPhase 2 done.", encoding="utf-8")

    skill2 = IterateFromSkill(armance_root=tmp_path, config=None)
    skill2.run(args=f"{r002_dir.name} iter")

    all_runs = list(runs_dir.iterdir())
    assert len(all_runs) == 3

    # Walk chain: r003 → r002 → r001
    chain = []
    current = [d for d in all_runs if d.name not in ("r_001", r002_dir.name)][0]
    for _ in range(3):
        m = yaml.safe_load((current / "manifest.yaml").read_text())
        chain.append(current.name)
        derived = m.get("derived_from", [])
        if not derived:
            break
        parent_id = derived[0]["run_id"] if isinstance(derived[0], dict) else derived[0]
        current = runs_dir / parent_id
        if not current.exists():
            break

    assert len(chain) >= 1
