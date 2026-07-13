"""DesignWorkflowSkill — parse + validate + write Kim's workflow YAML.

The skill is intentionally thin: Kim (LLM) holds the dialogue and produces
the full YAML block inline. The skill extracts it, validates against the
Workflow schema, and writes the file with rationale comments. No state
machine, no "tape ok" prompts — those are Kim's job in plain language.

Spec: docs/spec/21_workflow_design.md (rewritten 2026-05-17)
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from armance.nls import t
from armance.service.skills.base import Skill
from armance.service.workflow_validation import validate_workflow_data
from armance.service.workflow_yaml_writer import write_workflow_yaml

logger = logging.getLogger(__name__)


# Canonical strategy keys (legacy short/standard/deep are accepted as aliases).
_STRATEGIES = {
    "rapide": {"label": "Rapide", "complexity": "minimal"},
    "equilibree": {"label": "Équilibrée", "complexity": "modéré"},
    "approfondie": {"label": "Approfondie", "complexity": "élevé"},
    "custom": {"label": "Custom", "complexity": "variable"},
}

_STRATEGY_ALIASES = {
    "short": "rapide",
    "standard": "equilibree",
    "deep": "approfondie",
    "rapide": "rapide",
    "equilibree": "equilibree",
    "équilibrée": "equilibree",
    "approfondie": "approfondie",
    "custom": "custom",
}

_YAML_FENCE_RE = re.compile(r"```(?:yaml)?\s*\n(.*?)\n```", flags=re.DOTALL)


class DesignWorkflowSkill(Skill):
    """Parse Kim's inline YAML, validate, write the workflow file."""

    description = "Validate + persist a workflow YAML produced by Kim."
    input_schema = {
        "type": "object",
        "properties": {
            "yaml_block": {"type": "string"},
        },
        "required": ["yaml_block"],
    }
    output_schema = {"type": "string"}

    slash = "/workflow design"
    nl_patterns = [
        r"construis[\s-]moi\s+un\s+workflow",
        r"j['']aimerais\s+un\s+workflow",
        r"aide[\s-]moi\s+à\s+designer",
        r"design\s+a\s+workflow",
        r"build\s+me\s+a\s+workflow",
        r"create\s+a\s+workflow",
        r"let['']s\s+create\s+a\s+workflow",
    ]
    triggered_by = "user"

    def __init__(
        self,
        armance_root: Path,
        config: Any,
        agents: list[Any] | None = None,
        project_brief: str = "",
    ) -> None:
        self.armance_root = armance_root
        self.config = config
        self._agents = agents or []
        self._project_brief = project_brief
        # Kept for back-compat with handlers' session-restore plumbing.
        self.state: str = "S0"
        self._name: str = ""
        self._intent: str = ""
        self._skeleton_key: str = ""
        self._draft_steps: list[dict[str, Any]] = []
        self._inputs: list[dict[str, Any]] = []
        self._default_mode: str = "full"
        self._rationale_lines: list[str] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, args: str = "", ctx: dict[str, Any] | None = None) -> str:
        """Parse the YAML block from Kim's reply (passed in ``args``),
        validate it, write the workflow. Returns a single-line confirmation
        or a structured error explaining what's missing — Kim reads this
        back and explains it to the user in plain language.
        """
        raw = args or ""
        yaml_text = self._extract_yaml(raw)
        if not yaml_text:
            logger.warning(
                "design: no YAML extracted. raw=%r", raw[:500],
            )
            self.state = "finished"
            return t("workflow.design_missing_yaml")

        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            logger.warning(
                "design: YAML parse error %s. yaml_text=%r", exc, yaml_text[:500],
            )
            self.state = "finished"
            return t("workflow.design_invalid_yaml", error=str(exc))

        ok, err, prompt_warnings = validate_workflow_data(data, self._agents)
        if not ok:
            logger.warning(
                "design: validation failed (%s). yaml_text=%r data_type=%s data=%r",
                err, yaml_text[:500], type(data).__name__, data,
            )
            self.state = "finished"
            return t("workflow.design_invalid_workflow", error=err)

        name = data["name"]
        steps = data["steps"]
        strategy = _STRATEGY_ALIASES.get(
            str(data.get("strategy", "")).lower().strip(), "custom"
        )

        self._name = name
        self._draft_steps = steps
        self._skeleton_key = strategy
        self._rationale_lines = [
            f"intent: {self._intent or self._project_brief or '(none)'}",
            f"strategy: {strategy}",
        ]

        scope = str(data.get("scope", "")).strip()
        path = write_workflow_yaml(
            workflows_dir=self.armance_root / ".armance" / "workflows",
            name=name,
            steps=steps,
            description=data.get("description", ""),
            inputs=data.get("inputs"),
            default_mode="full",
            rationale="\n".join(self._rationale_lines),
            dry_run=False,
            scope=scope,
        )
        self.state = "finished"
        meta = _STRATEGIES.get(strategy, _STRATEGIES["custom"])

        # Build a short, human-readable summary of what was saved so Kim
        # can echo it back in NL instead of dropping raw YAML on the user.
        step_lines = []
        for s in steps:
            r = s.get("role") or s.get("domain") or "?"
            step_lines.append(f"  {s.get('id', '?')} ({s.get('kind', '?')} · {r})")

        summary = (
            f"Workflow **{name}** créé — stratégie {meta['label']} "
            f"({meta['complexity']}). {len(steps)} étape(s):\n"
            + "\n".join(step_lines)
            + "\n\nFichier : `.armance/workflows/"
            + (path.name if path else f"{name}.yaml")
            + "`. Le workflow est **construit, pas encore lancé** — "
            "demandez explicitement à l'exécuter pour démarrer un run."
        )
        if prompt_warnings:
            summary += "\n\n" + t("workflow.design_prompt_warnings") + "\n" + "\n".join(
                f"- {w}" for w in prompt_warnings
            )
        return summary

    # ------------------------------------------------------------------
    # YAML extraction + validation
    # ------------------------------------------------------------------

    def _extract_yaml(self, raw: str) -> str:
        """Pull out the first ```yaml ... ``` (or generic ``` ... ```) block
        from Kim's reply. Falls back to bare-YAML detection when no fence.

        Defensive trim: strips stray fence markers (``` and bare 'yaml' lines)
        that weak LLMs sprinkle around the body. Without this, a single
        orphan ``` at the end causes `yaml.safe_load` to ScannerError.
        """
        # Prefer the first fence whose body contains both `name:` and
        # `steps:`. Weak LLMs sometimes wrap the [EXECUTE:/...] tag itself
        # in a fence and put the real YAML in a *second* fence — picking
        # the first fence blindly would capture only the tag.
        for m in _YAML_FENCE_RE.finditer(raw):
            body = m.group(1)
            if "name:" in body and "steps:" in body:
                return body.strip()
        m = _YAML_FENCE_RE.search(raw)
        if m:
            return m.group(1).strip()
        # Fallback: bare YAML — extract from first `name:` line to end.
        # Avoids passing leading prose to yaml.safe_load (→ "racine non-objet").
        if "name:" in raw and "steps:" in raw:
            idx = raw.find("name:")
            tail = raw[idx:]
            # Drop any stray fence lines (orphan ``` or bare "yaml") that
            # would break the parser.
            cleaned_lines = [
                line for line in tail.splitlines()
                if line.strip() not in ("```", "```yaml", "yaml")
            ]
            return "\n".join(cleaned_lines).strip()
        return ""

