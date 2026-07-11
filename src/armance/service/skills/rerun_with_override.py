"""RerunWithOverrideSkill — partial re-run with human output override (Lot I).

Need: "I reworked step B's output BY HAND — feed it to step C WITHOUT re-running
B." A partial re-run from a resume point, injecting a human-edited output for one
or more upstream steps, re-running only what is downstream.

Invariant honoured: a run NEVER overwrites a run. This mints a NEW run (via
`create_run`) whose manifest records `derived_from: [{run_id, overrides:[…]}]`
and leaves the parent untouched.

Layering: override files are read HERE (service side) and injected via the
`provided_outputs` dict threaded into `_cmd_workflow_run` → the engine sees the
overridden step's output already in hand and does not call the runner for it
(status `provided`). `core` does no I/O and no loop.

Design (§6.8): a DEDICATED skill on the REAL infra (`create_run` + the real
`_cmd_workflow_run` `inputs`/runner seam), NOT the stale `iterate_from.py` fake
`workflows/runs/*/manifest.yaml` layout. `iterate_from` is left untouched.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from armance.service.skills.base import Skill

logger = logging.getLogger(__name__)

_OVERRIDE_RE = re.compile(r"^(?P<step>[^=]+)=(?P<file>.+)$")


def parse_rerun_args(args: str) -> dict[str, Any]:
    """Parse `<workflow> <parent_run_id> --override-step <id>=<file> [...]
    [--from-step <id>]`. Returns a dict or raises ValueError with usage."""
    tokens = args.strip().split()
    if len(tokens) < 2:
        raise ValueError(
            "Usage : `/workflow rerun <workflow> <parent_run_id> "
            "--override-step <step_id>=<fichier> [--override-step …] "
            "[--from-step <step_id>]`"
        )
    workflow = tokens[0]
    parent_run_id = tokens[1]
    overrides: dict[str, str] = {}
    from_step: str | None = None
    i = 2
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("--override-step", "--override", "-o"):
            i += 1
            if i >= len(tokens):
                raise ValueError("--override-step needs <step_id>=<fichier>")
            m = _OVERRIDE_RE.match(tokens[i])
            if not m:
                raise ValueError(
                    f"override mal formé : `{tokens[i]}` (attendu <step_id>=<fichier>)"
                )
            overrides[m.group("step").strip()] = m.group("file").strip()
        elif tok in ("--from-step", "--from", "-f"):
            i += 1
            if i >= len(tokens):
                raise ValueError("--from-step needs <step_id>")
            from_step = tokens[i].strip()
        else:
            m = _OVERRIDE_RE.match(tok)
            if m:  # bare `id=file` also accepted
                overrides[m.group("step").strip()] = m.group("file").strip()
            else:
                raise ValueError(f"argument inconnu : `{tok}`")
        i += 1
    if not overrides:
        raise ValueError("au moins un `--override-step <step_id>=<fichier>` est requis")
    return {
        "workflow": workflow,
        "parent_run_id": parent_run_id,
        "overrides": overrides,
        "from_step": from_step,
    }


class RerunWithOverrideSkill(Skill):
    """Partial re-run of a workflow with per-step human output override."""

    description = (
        "Reprend un run existant en réinjectant un output édité à la main pour "
        "un/plusieurs steps amont (sans les re-jouer) et ne ré-exécute que l'aval ; "
        "crée un nouveau run (derived_from), sans jamais écraser le parent."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "workflow": {"type": "string"},
            "parent_run_id": {"type": "string"},
            "overrides": {"type": "object"},
            "from_step": {"type": ["string", "null"]},
        },
        "required": ["workflow", "parent_run_id", "overrides"],
    }
    output_schema = {"type": "string", "description": "New run id or error."}

    slash = "/workflow-rerun"
    triggered_by = "user"

    def __init__(self, armance_root: Path) -> None:
        self.armance_root = armance_root

    def read_overrides(self, overrides: dict[str, str]) -> dict[str, str]:
        """Read each override file (service-side I/O). Missing/unreadable files
        raise ValueError so the caller reports it instead of running blind."""
        out: dict[str, str] = {}
        for step_id, spec in overrides.items():
            path = Path(spec)
            if not path.is_absolute():
                path = self.armance_root / spec
            if not path.is_file():
                raise ValueError(f"fichier d'override introuvable pour `{step_id}` : {spec}")
            out[step_id] = path.read_text(encoding="utf-8")
        return out

    def load_parent_outputs(self, workflow: str, parent_run_id: str) -> dict[str, str]:
        """Carry the parent run's per-step outputs so non-overridden upstream
        steps keep their original output instead of re-running."""
        from armance.service.workflow_runs import load_run

        run_dir = load_run(self.armance_root, workflow, parent_run_id)
        outputs: dict[str, str] = {}
        for fname, content in run_dir.items():
            m = re.match(r"^step-(?P<id>.+)\.md$", fname)
            if m and not fname.endswith(".prompt.md"):
                outputs[m.group("id")] = content
        return outputs

    def build_plan(
        self,
        parent_run_id: str,
        override_texts: dict[str, str],
        parent_outputs: dict[str, str],
        from_step: str | None,
        deps: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Compute provided_outputs (overrides + carried upstream) + derived_from.

        `deps` maps step id → its `depends_on`. A step RE-RUNS iff it is the
        resume point (`from_step`) or a transitive descendant of an override /
        of the resume point. Everything else is `provided` verbatim (overrides
        with the human text, other upstream parent steps carried unchanged) so
        it is never re-executed. Sources track provenance.
        """
        rerun_roots = set(override_texts)
        if from_step is not None:
            rerun_roots.add(from_step)
        rerun = self._descendants(rerun_roots, deps)
        # The resume step itself + descendants re-run; overrides are provided.
        rerun -= set(override_texts)

        provided: dict[str, str] = {}
        sources: dict[str, str] = {}
        for sid, text in override_texts.items():
            provided[sid] = text
            sources[sid] = "override-file"
        for sid, text in parent_outputs.items():
            if sid in provided or sid in rerun:
                continue
            provided[sid] = text
            sources[sid] = f"parent:{parent_run_id}"
        derived = [{
            "run_id": parent_run_id,
            "overrides": [{"step": sid, "source": "override-file"} for sid in override_texts],
            "from_step": from_step,
        }]
        return {"provided": provided, "sources": sources, "derived_from": derived}

    @staticmethod
    def _descendants(roots: set[str], deps: dict[str, list[str]]) -> set[str]:
        """All steps that are `roots` or transitively depend on a root."""
        result = set(roots)
        changed = True
        while changed:
            changed = False
            for sid, sdeps in deps.items():
                if sid in result:
                    continue
                if any(d in result for d in sdeps):
                    result.add(sid)
                    changed = True
        return result
