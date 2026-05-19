"""Tests for R-05: Skill base class and MCP-shape fields on all skills."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# base.py exists and has the required fields
# ---------------------------------------------------------------------------


def test_skill_base_importable() -> None:
    from armance.service.skills.base import Skill  # noqa: F401


def test_skill_base_has_description() -> None:
    from armance.service.skills.base import Skill
    assert hasattr(Skill, "description")


def test_skill_base_has_input_schema() -> None:
    from armance.service.skills.base import Skill
    assert hasattr(Skill, "input_schema")


def test_skill_base_has_output_schema() -> None:
    from armance.service.skills.base import Skill
    assert hasattr(Skill, "output_schema")


# ---------------------------------------------------------------------------
# Concrete skills inherit from Skill and declare input_schema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module,cls", [
    ("armance.service.skills.iterate_from", "IterateFromSkill"),
    ("armance.service.skills.set_brief", "SetBriefSkill"),
    ("armance.service.skills.set_l1", "SetL1Skill"),
    ("armance.service.skills.design_workflow", "DesignWorkflowSkill"),
    ("armance.service.skills.feedback_loop", "FeedbackLoopSkill"),
])
def test_skill_declares_input_schema(module: str, cls: str) -> None:
    import importlib
    mod = importlib.import_module(module)
    skill_cls = getattr(mod, cls)
    assert hasattr(skill_cls, "input_schema"), f"{cls} missing input_schema"


@pytest.mark.parametrize("module,cls", [
    ("armance.service.skills.iterate_from", "IterateFromSkill"),
    ("armance.service.skills.set_brief", "SetBriefSkill"),
    ("armance.service.skills.set_l1", "SetL1Skill"),
    ("armance.service.skills.design_workflow", "DesignWorkflowSkill"),
    ("armance.service.skills.feedback_loop", "FeedbackLoopSkill"),
])
def test_skill_inherits_from_base(module: str, cls: str) -> None:
    import importlib
    from armance.service.skills.base import Skill
    mod = importlib.import_module(module)
    skill_cls = getattr(mod, cls)
    assert issubclass(skill_cls, Skill), f"{cls} does not inherit from Skill"


def test_skill_description_is_str() -> None:
    from armance.service.skills.iterate_from import IterateFromSkill
    assert isinstance(IterateFromSkill.description, str)
    assert IterateFromSkill.description


def test_skill_input_schema_is_dict() -> None:
    from armance.service.skills.iterate_from import IterateFromSkill
    assert isinstance(IterateFromSkill.input_schema, dict)


def test_skill_output_schema_is_dict() -> None:
    from armance.service.skills.iterate_from import IterateFromSkill
    assert isinstance(IterateFromSkill.output_schema, dict)
