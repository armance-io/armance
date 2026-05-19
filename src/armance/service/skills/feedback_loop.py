"""FeedbackLoopSkill — workflow synthesis → L0 v+1.

After a workflow run with ≥1 judge step, Kim proposes integrating
the synthesis into the project brief (L0). User must confirm explicitly;
only then is confirmed_by_user: true written.

Spec: docs/spec/22_circular_outputs.md § 2. Skill feedback_loop
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from armance.service.context_service import ContextService
from armance.service.skills.base import Skill

logger = logging.getLogger(__name__)

_CONFIRM_TOKENS = frozenset({"oui", "yes", "ok", "confirm", "confirme", "go"})
_DECLINE_TOKENS = frozenset({"non", "no", "nope", "skip", "annule", "cancel"})


class FeedbackLoopSkill(Skill):
    """Propose merging a workflow synthesis into L0, then confirm or decline."""

    description = "Propose integrating a workflow synthesis into the project brief (L0 v+1), requiring explicit user confirmation."
    input_schema = {
        "type": "object",
        "properties": {
            "synthesis": {"type": "string", "description": "Synthesis text to fold into L0."},
            "confirmed": {"type": "boolean", "description": "True if user confirmed the merge."},
        },
        "required": ["synthesis"],
    }
    output_schema = {"type": "string", "description": "Result message or path of updated L0."}

    slash = "/feedback-loop"
    nl_patterns = [
        r"intègre\s+la\s+synthèse",
        r"mets?\s+à\s+jour\s+le\s+brief",
        r"fold\s+this\s+into\s+the\s+brief",
        r"update\s+the\s+l0",
    ]
    triggered_by = "user"

    def __init__(
        self,
        armance_root: Path,
        config: Any,
    ) -> None:
        self.armance_root = armance_root
        self.config = config
        self._ctx = ContextService(armance_root)

        self._pending_synthesis: str = ""
        self._pending_run_id: str = ""
        self._pending_merged_body: str = ""
        self._state: str = "idle"  # idle | proposed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def propose(self, synthesis: str, run_id: str) -> str:
        """Present a diff-like preview of the proposed L0 update."""
        self._pending_synthesis = synthesis
        self._pending_run_id = run_id

        current_body = self._ctx.read_l0_body() or "(empty)"
        merged = self._merge(current_body, synthesis)
        self._pending_merged_body = merged

        self._state = "proposed"
        return (
            f"**Feedback loop** — run `{run_id}`\n\n"
            "Je propose d'intégrer cette synthèse dans le brief (L0).\n\n"
            "**Ajouts proposés :**\n"
            f"{self._diff_preview(current_body, merged)}\n\n"
            "Tape `oui` pour confirmer ou `non` pour annuler."
        )

    def confirm(self) -> str:
        """Write the merged L0 with confirmed_by_user=True."""
        if self._state != "proposed":
            return "Rien à confirmer. Lance d'abord `/feedback-loop <run-id>`."

        derived = [f"workflows/runs/{self._pending_run_id}/judge"]
        path = self._ctx.write_l0(
            body=self._pending_merged_body,
            slug=re.sub(r"[^\w-]", "-", self._pending_run_id)[:30],
            confirmed_by_user=True,
            derived_from=derived,
        )
        self._state = "idle"
        return (
            f"Contexte mis à jour ✓\n"
            f"Écrit dans `.armance/{path.relative_to(self.armance_root)}`\n"
            f"`confirmed_by_user: true` — `derived_from: {derived}`"
        )

    def decline(self) -> str:
        """Discard the proposal without writing."""
        run_id = self._pending_run_id
        self._state = "idle"
        self._pending_synthesis = ""
        self._pending_merged_body = ""
        return (
            f"OK, je n'ai pas modifié le contexte. "
            f"Tu peux relancer la mise à jour plus tard avec `/feedback-loop {run_id}`."
        )

    def run(self, args: str = "", ctx: dict[str, Any] | None = None) -> str:
        """Entry point for /feedback-loop command or confirmation turn."""
        token = args.strip().lower()
        if self._state == "proposed":
            if token in _CONFIRM_TOKENS:
                return self.confirm()
            if token in _DECLINE_TOKENS:
                return self.decline()
            return (
                f"Tape `oui` pour confirmer ou `non` pour annuler.\n"
                f"Run en attente : `{self._pending_run_id}`"
            )
        # If called with a run_id arg, load the synthesis and propose
        if args.strip():
            run_id = args.strip().split()[0]
            synthesis = self._load_synthesis(run_id)
            return self.propose(synthesis=synthesis, run_id=run_id)
        return "Usage : `/feedback-loop <run-id>` ou confirme une proposition en attente."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _merge(self, current: str, synthesis: str) -> str:
        """Append the Recommendation (or Consensus) from synthesis to the L0 body."""
        rec = self._extract_section(synthesis, "Recommendation") or self._extract_section(
            synthesis, "Consensus"
        )
        if not rec:
            # Fallback: first non-empty, non-heading line
            rec = next(
                (ln.strip() for ln in synthesis.splitlines() if ln.strip() and not ln.startswith("#")),
                "(synthesis contenu non extrait)",
            )

        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        addition = (
            f"\n\n### Decisions made ({today})\n"
            f"- {rec}\n"
            f"  *(derived from run `{self._pending_run_id}`)*"
        )
        return current + addition

    @staticmethod
    def _extract_section(text: str, section: str) -> str:
        """Return body of the first ## <section> block, stripped."""
        sections = re.split(r"^(?=##)", text, flags=re.MULTILINE)
        for s in sections:
            if re.match(rf"##\s*{re.escape(section)}\b", s, re.IGNORECASE):
                body = s.split("\n", 1)[1] if "\n" in s else ""
                return body.strip()
        return ""

    def _diff_preview(self, before: str, after: str) -> str:
        before_lines = set(before.splitlines())
        added = [f"+ {line}" for line in after.splitlines() if line not in before_lines and line.strip()]
        return "\n".join(added[:10]) or "(aucune différence détectée)"

    def _load_synthesis(self, run_id: str) -> str:
        """Load the highest-version judge deliverable from a run directory."""
        run_dir = self.armance_root / "workflows" / "runs" / run_id
        if not run_dir.exists():
            return f"(synthesis for run {run_id} not found)"
        deliverables = sorted(
            run_dir.glob("**/judge_v*.md"),
            key=lambda p: int(p.stem.split("_v")[-1]) if "_v" in p.stem and p.stem.split("_v")[-1].isdigit() else 0,
        )
        if deliverables:
            return deliverables[-1].read_text(encoding="utf-8")
        return f"(synthesis for run {run_id} not found)"
