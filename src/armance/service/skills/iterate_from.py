"""IterateFromSkill — spawn workflow N+1 from workflow N's synthesis.

Preserves derived_from chain in the new run's manifest.yaml.
The synthesis TEXT is passed as user_prompt, not a file pointer.

Spec: docs/spec/22_circular_outputs.md § 3. Skill iterate_from
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from armance.service.skills.base import Skill

logger = logging.getLogger(__name__)


class IterateFromSkill(Skill):
    """Spawn a new workflow run seeded with a prior run's synthesis."""

    description = "Spawn workflow N+1 from workflow N's synthesis, preserving the derived_from chain."
    input_schema = {
        "type": "object",
        "properties": {
            "source_run_id": {"type": "string", "description": "Run ID to iterate from."},
            "workflow_name": {"type": "string", "description": "Target workflow name (optional)."},
        },
        "required": ["source_run_id"],
    }
    output_schema = {"type": "string", "description": "New run ID or error message."}

    slash = "/iterate-from"
    nl_patterns = [
        r"lance\s+un\s+nouveau\s+workflow\s+basé\s+sur",
        r"continue\s+à\s+partir\s+de\s+wf:",
        r"iterate\s+from\s+r_\w+",
        r"spin\s+a\s+new\s+run\s+from\s+this\s+synthesis",
    ]
    triggered_by = "user"

    def __init__(self, armance_root: Path, config: Any) -> None:
        self.armance_root = armance_root
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, args: str = "", ctx: dict[str, Any] | None = None) -> str:
        """Entry point. args = '<source_run_id> [<workflow_name>]'."""
        parts = args.strip().split()
        if not parts:
            return "Usage : `/iterate-from <run-id> [<workflow-name>]`"

        source_run_id = parts[0]
        workflow_name = parts[1] if len(parts) > 1 else None

        synthesis = self._load_synthesis(source_run_id)
        if not workflow_name:
            workflow_name = self._propose_workflow(synthesis)
            if not workflow_name:
                return (
                    "Aucun workflow trouvé dans `.armance/workflows/`. "
                    "Crée-en un avec `/workflow design <nom>` d'abord."
                )

        new_run_id = self._spawn_run(
            source_run_id=source_run_id,
            workflow_name=workflow_name,
            synthesis=synthesis,
        )
        return (
            f"Nouveau run `{new_run_id}` créé à partir de `{source_run_id}`.\n"
            f"Workflow : `{workflow_name}`\n"
            f"Invite les agents avec `/workflow run {workflow_name}` "
            f"ou suis le run `{new_run_id}`."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_synthesis(self, run_id: str) -> str:
        run_dir = self.armance_root / "workflows" / "runs" / run_id
        if run_dir.exists():
            deliverables = sorted(
                run_dir.glob("**/judge_v*.md"),
                key=lambda p: int(p.stem.split("_v")[-1]) if "_v" in p.stem and p.stem.split("_v")[-1].isdigit() else 0,
            )
            if deliverables:
                return deliverables[-1].read_text(encoding="utf-8")
        return f"(synthesis for run {run_id} not found)"

    def _propose_workflow(self, synthesis: str) -> str | None:
        """Return first available workflow name, or None."""
        wf_dir = self.armance_root / ".armance" / "workflows"
        if not wf_dir.exists():
            return None
        yamls = [f.stem for f in sorted(wf_dir.glob("*.yaml"))]
        return yamls[0] if yamls else None

    def _spawn_run(self, source_run_id: str, workflow_name: str, synthesis: str) -> str:
        new_run_id = f"r_{uuid.uuid4().hex[:8]}"
        run_dir = self.armance_root / "workflows" / "runs" / new_run_id
        run_dir.mkdir(parents=True)

        # Load source manifest to record the deliverable path
        source_dir = self.armance_root / "workflows" / "runs" / source_run_id
        deliverables = list(source_dir.glob("**/judge_v*.md")) if source_dir.exists() else []
        deliverable_rel = str(deliverables[-1].relative_to(self.armance_root)) if deliverables else ""

        manifest = {
            "run_id": new_run_id,
            "workflow": workflow_name,
            "status": "submitted",
            "started_at": datetime.now(tz=timezone.utc).isoformat(),
            "user_prompt": synthesis,  # text, not file pointer
            "derived_from": [
                {
                    "run_id": source_run_id,
                    "workflow": self._source_workflow(source_run_id),
                    "deliverable": deliverable_rel,
                }
            ],
        }
        (run_dir / "manifest.yaml").write_text(
            yaml.dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("Spawned iterate run %s from %s", new_run_id, source_run_id)
        return new_run_id

    def _source_workflow(self, run_id: str) -> str:
        manifest_path = self.armance_root / "workflows" / "runs" / run_id / "manifest.yaml"
        if manifest_path.exists():
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            return data.get("workflow", "")
        return ""
