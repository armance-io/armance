"""Tests for the A2 extra validation helpers (structure + prompt refs).

Repro data comes from a real broken run: tmp/runtime3/workflows/
reponse-technique-short.yaml had a `depends_on` pointing at a step that
never existed, and a step whose `role` was actually another step's id.
"""
from __future__ import annotations

from armance.service.workflow_validation import (
    validate_prompt_templates,
    validate_step_structure,
)


def test_depends_on_unknown_step_is_rejected() -> None:
    steps = [
        {"id": "a", "kind": "task", "role": "infra", "depends_on": []},
        {"id": "b", "kind": "task", "role": "ml", "depends_on": ["extraire_exigences"]},
    ]
    err = validate_step_structure(steps)
    assert "extraire_exigences" in err
    assert "b" in err


def test_role_equal_to_step_id_is_rejected() -> None:
    steps = [
        {"id": "synthese_mona", "kind": "judge", "role": "mona", "depends_on": []},
        {"id": "revision_finale", "kind": "task", "role": "synthese_mona",
         "depends_on": ["synthese_mona"]},
    ]
    err = validate_step_structure(steps)
    assert "revision_finale" in err
    assert "synthese_mona" in err


def test_structurally_sound_workflow_passes() -> None:
    steps = [
        {"id": "a", "kind": "task", "role": "infra", "depends_on": []},
        {"id": "b", "kind": "judge", "role": "mona", "depends_on": ["a"]},
    ]
    assert validate_step_structure(steps) == ""


def test_template_ref_to_valid_dependency_passes() -> None:
    steps = [
        {"id": "a", "kind": "task", "role": "infra", "depends_on": [],
         "prompt_template": "Do X."},
        {"id": "b", "kind": "judge", "role": "mona", "depends_on": ["a"],
         "prompt_template": "Synthesise {{a.output}}."},
    ]
    err, warnings = validate_prompt_templates(steps)
    assert err == ""
    assert warnings == []


def test_template_ref_to_undeclared_dependency_is_rejected() -> None:
    steps = [
        {"id": "a", "kind": "task", "role": "infra", "depends_on": [],
         "prompt_template": "Do X."},
        {"id": "b", "kind": "judge", "role": "mona", "depends_on": [],
         "prompt_template": "Synthesise {{a.output}}."},
    ]
    err, warnings = validate_prompt_templates(steps)
    assert "b" in err
    assert "a.output" in err


def test_template_ref_to_user_prompt_passes() -> None:
    steps = [
        {"id": "a", "kind": "task", "role": "infra", "depends_on": [],
         "prompt_template": "Handle {{user_prompt}}."},
    ]
    err, warnings = validate_prompt_templates(steps)
    assert err == ""


def test_template_ref_to_declared_input_passes() -> None:
    steps = [
        {"id": "a", "kind": "task", "role": "infra", "depends_on": [],
         "prompt_template": "Seed: {{seed.doc}}."},
    ]
    err, warnings = validate_prompt_templates(steps, declared_inputs={"seed.doc"})
    assert err == ""


def test_empty_prompt_template_on_task_is_warning_not_error() -> None:
    steps = [
        {"id": "a", "kind": "task", "role": "infra", "depends_on": []},
    ]
    err, warnings = validate_prompt_templates(steps)
    assert err == ""
    assert len(warnings) == 1
    assert "a" in warnings[0]


def test_empty_prompt_template_on_human_checkpoint_no_warning() -> None:
    steps = [
        {"id": "a", "kind": "human_checkpoint", "depends_on": []},
    ]
    err, warnings = validate_prompt_templates(steps)
    assert err == ""
    assert warnings == []
