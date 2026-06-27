"""JudgeAgent — Mona's LLM-as-judge with claim verification.

Implements T-20: synthesise N deliverables into one structured synthesis.
Claims from the ledger are injected into the prompt; unsourced claims
are surfaced in a dedicated block.

Spec: docs/spec/03_agents.md § Mona, docs/spec/19_claim_ledger.md § Mona-judge
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from armance.service.claim_ledger_service import ClaimLedgerService
from armance.service.llm_service import call_with_ledger, get_client

logger = logging.getLogger(__name__)

_WARNING_BANNER = (
    "⚠ AUCUNE CLAIM SOURCÉE dans le registre pour cette vue. "
    "La synthèse ne peut pas être vérifiée contre des sources enregistrées.\n\n"
)

_SYNTHESIS_INSTRUCTION = """\
## Claim references

The following claims were registered in the ledger for this view.
Every Consensus and Recommendation statement MUST carry at least one `(c_<id>)` reference.
Claims with empty evidence must be placed in the "Unsourced claims" block.

{claims_block}

## Output format (required)

- **Consensus** — convergence points, each with `(c_<id>)` parens.
- **Divergence** — productive disagreements with brief reasoning.
- **Blind spots** — what the panel missed.
- **Unsourced claims** — claims with no evidence in the ledger.
- **Recommendation** — ranked next steps, each with `(c_<id>)` refs.
"""

_NO_CLAIMS_INSTRUCTION = (
    "⚠ NO CLAIMS in the ledger for this view. "
    "You MUST prepend the warning banner to your synthesis:\n"
    "`⚠ AUCUNE CLAIM SOURCÉE — synthèse non vérifiable.`\n"
)


@dataclass
class Synthesis:
    """Result of a JudgeAgent.synthesise() call."""

    content: str
    view: str
    claim_count: int = 0


class JudgeAgent:
    """Mona — synthesises specialist deliverables with claim verification."""

    def __init__(self, armance_root: Path, config: Any) -> None:
        self.armance_root = armance_root
        self.config = config
        self._ledger = ClaimLedgerService(armance_root)

    async def synthesise(
        self,
        view: str,
        deliverables: list[str],
    ) -> Synthesis:
        """Synthesise deliverables for a view into a structured report.

        Steps:
        1. Query ledger for all claims in the view.
        2. Build system prompt with claim context.
        3. Call LLM (Mona's builtin).
        4. Return Synthesis.
        """
        claims = self._ledger.get_claims_by_view(view)

        # Build system prompt
        system_prompt = self._build_system_prompt(claims)

        # Build user message from deliverables
        deliverables_text = "\n\n---\n\n".join(
            f"### Deliverable {i + 1}\n\n{d}" for i, d in enumerate(deliverables)
        )
        user_message = (
            f"Synthesise the following {len(deliverables)} deliverable(s) "
            f"for view `{view}`:\n\n{deliverables_text}"
        )

        mona = self._load_mona()
        client = get_client(mona.provider, self.config)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        extras: dict[str, Any] = {}
        if mona.reasoning:
            extras["reasoning"] = {"effort": mona.reasoning}

        response = await call_with_ledger(
            client, mona.name, messages, mona.model,
            provider=mona.provider, **extras
        )

        synthesis = Synthesis(
            content=response.text,
            view=view,
            claim_count=len(claims),
        )

        # T-24: append to shared_memory/decisions.md
        self._append_decision(synthesis)

        return synthesis

    def _build_system_prompt(self, claims: list) -> str:

        mona = self._load_mona()
        base_prompt = mona.effective_system_prompt(caveman_level="none")

        if not claims:
            return f"{base_prompt}\n\n{_NO_CLAIMS_INSTRUCTION}"

        # Build claims block: one line per claim
        lines: list[str] = []
        for claim in claims:
            evidence_note = (
                ", ".join(e.ref for e in claim.evidence)
                if claim.evidence
                else "— no evidence"
            )
            lines.append(
                f"- `{claim.id}` by {claim.by}: {claim.text} [{evidence_note}]"
            )
        claims_block = "\n".join(lines)

        instruction = _SYNTHESIS_INSTRUCTION.format(claims_block=claims_block)
        return f"{base_prompt}\n\n{instruction}"

    def _append_decision(self, synthesis: Synthesis) -> None:
        """Append synthesis summary to shared_memory/decisions.md."""
        sm_dir = self.armance_root / "shared_memory"
        sm_dir.mkdir(parents=True, exist_ok=True)
        decisions_path = sm_dir / "decisions.md"

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        entry = f"\n## {now} — view: {synthesis.view}\n\n{synthesis.content.strip()}\n"

        if not decisions_path.exists():
            decisions_path.write_text(f"# Decisions\n{entry}", encoding="utf-8")
        else:
            with decisions_path.open("a", encoding="utf-8") as f:
                f.write(entry)

        logger.info("Appended decision to decisions.md (view=%s)", synthesis.view)

    def _load_mona(self):
        from armance.core.models.agent import Agent
        from armance import paths

        global_path = paths.global_agents_dir() / "system-judge.md"
        if global_path.exists():
            return Agent.load(global_path)



        # Minimal fallback
        return Agent(
            name="system-judge",
            role="meta",
            persona="balanced",
            provider="openrouter",
            model="openai/gpt-4o-mini",
            reasoning="medium",
            system_prompt="You are Mona, the synthesis judge.",
        )

    async def compile_assumptions(self, all_steps_text: str) -> str:
        """Analyze specialist deliverables, extract hypotheses/questions/assumptions,
        and synthesize them into a structured report.
        """
        system_prompt = (
            "You are Mona, the synthesis judge. You are reviewing the active brainstorming run.\n"
            "Your task is to analyze all the specialist outputs and deliverables from this run, "
            "identify all unstated assumptions, explicitly stated hypotheses (`HYPOTHESIS:`), "
            "and unresolved questions (`QUESTION:`).\n\n"
            "You must compile them into a structured Markdown document with two parts separated by a horizontal rule `---`:\n"
            "1. **Executive Summary** — A concise summary of the key critical uncertainties and assumptions made during this run.\n"
            "2. **Detailed Register** — An exhaustive table or list mapping each assumption, hypothesis, or question back to the specialist who raised it.\n\n"
            "Be direct, crisp, and strategic. Do not invent any new facts, simply synthesize what the specialists produced."
        )

        # Voice overlay so Mona's report follows the user's configured language.
        try:
            from armance.service.agents._voice_overlay import voice_overlay
            system_prompt = f"{system_prompt}\n\n{voice_overlay(getattr(self.config, 'language', 'en'))}"
        except Exception:
            pass

        mona = self._load_mona()
        client = get_client(mona.provider, self.config)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the text of all steps executed in this run:\n\n{all_steps_text}"},
        ]

        extras: dict[str, Any] = {}
        if mona.reasoning:
            extras["reasoning"] = {"effort": mona.reasoning}

        response = await call_with_ledger(
            client, mona.name, messages, mona.model,
            provider=mona.provider, **extras
        )
        return response.text
