"""Lot B — seed documents in a workflow run.

Design: roadmap/03_workflow_quality_refonte.md §4. Acceptance criterion:
run with a seed doc → the document's content appears in the root step's
prompt (so a specialist can challenge/extend an existing draft instead of
writing from scratch).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from armance.core.models.workflow import (
    Workflow,
    WorkflowStep,
    _compose_default_prompt,
    execute_workflow,
)
from armance.service.seed_docs import (
    MAX_SEED_CHARS,
    load_adhoc_seed_docs,
    load_library_seed_docs,
)


# --- core: default prompt surfaces seed docs -------------------------------

def test_default_prompt_injects_seed_document() -> None:
    step = WorkflowStep(id="analyse", kind="task", role="ml", seed_docs=["ao.md"])
    wf = Workflow(name="challenge", scope="challenge the tender", steps=[step])
    prompt = _compose_default_prompt(
        wf, step, user_prompt="challenge it", results={},
        inputs={"seed.ao.md": "TENDER BODY — section requirements..."},
    )
    assert "## Seed documents" in prompt
    assert "`ao.md`" in prompt
    assert "TENDER BODY — section requirements" in prompt


def test_default_prompt_no_seed_section_when_absent() -> None:
    step = WorkflowStep(id="x", kind="task", role="ml")
    wf = Workflow(name="w", steps=[step])
    prompt = _compose_default_prompt(wf, step, user_prompt="go", results={})
    assert "## Seed documents" not in prompt


# --- core: execute_workflow threads inputs into the root prompt ------------

def test_execute_workflow_seed_reaches_root_step_prompt() -> None:
    step = WorkflowStep(id="root", kind="task", role="ml", seed_docs=["ao.md"])
    wf = Workflow(name="challenge", scope="s", steps=[step])
    seen: dict[str, str] = {}

    async def runner(s: WorkflowStep, prompt: str) -> str:
        seen[s.id] = prompt
        return "ok"

    asyncio.run(
        execute_workflow(
            wf, user_prompt="challenge", runner=runner,
            inputs={"seed.ao.md": "SECRET TENDER TEXT"},
        )
    )
    assert "SECRET TENDER TEXT" in seen["root"]


def test_execute_workflow_seed_via_template_ref() -> None:
    step = WorkflowStep(
        id="root", kind="task", role="ml",
        prompt_template="Challenge this: {{seed.ao.md}}",
    )
    wf = Workflow(name="challenge", steps=[step])
    seen: dict[str, str] = {}

    async def runner(s: WorkflowStep, prompt: str) -> str:
        seen[s.id] = prompt
        return "ok"

    asyncio.run(
        execute_workflow(
            wf, user_prompt="x", runner=runner,
            inputs={"seed.ao.md": "TENDER-123"},
        )
    )
    assert "Challenge this: TENDER-123" in seen["root"]


# --- service: library + ad-hoc loaders -------------------------------------

def test_load_library_seed_docs_reads_and_caps(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "ao.md").write_text("A" * (MAX_SEED_CHARS + 500), encoding="utf-8")
    out = load_library_seed_docs(tmp_path, ["ao.md"])
    assert "seed.ao.md" in out
    assert len(out["seed.ao.md"]) == MAX_SEED_CHARS


def test_load_library_seed_docs_missing_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    out = load_library_seed_docs(tmp_path, ["nope.md"])
    assert out == {}


def test_load_adhoc_seed_docs_key_equals_path(tmp_path: Path) -> None:
    f = tmp_path / "draft.txt"
    f.write_text("DRAFT CONTENT", encoding="utf-8")
    out = load_adhoc_seed_docs([f"tender={f}"])
    assert out == {"seed.tender": "DRAFT CONTENT"}


def test_load_adhoc_seed_docs_bare_path_uses_stem(tmp_path: Path) -> None:
    f = tmp_path / "draft.txt"
    f.write_text("DRAFT CONTENT", encoding="utf-8")
    out = load_adhoc_seed_docs([str(f)])
    assert out == {"seed.draft": "DRAFT CONTENT"}


def test_load_adhoc_seed_docs_missing_file_skipped() -> None:
    out = load_adhoc_seed_docs(["/nonexistent/path/x.md"])
    assert out == {}
