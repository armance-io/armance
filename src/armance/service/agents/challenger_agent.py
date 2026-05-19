"""ChallengerAgent — Serge, the adversary.

Implements T-25a: red-team pressure on any synthesis. Output is the
rigid 4-block critique format. Cross-family check is a hard constraint.

Spec: docs/spec/03_agents.md § Serge, docs/spec/19_claim_ledger.md § Serge.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from armance.storage.rag_index import RagService

from armance.service.claim_ledger_service import ClaimLedgerService
from armance.service.llm_service import call_with_ledger, get_client

logger = logging.getLogger(__name__)

# Phrases that indicate genuine objections (not "no objections")
# These are affirmative objection phrases — not preceded by negation
_OBJECTION_PHRASES = [
    r"(?<!no\s)(?<!not\s)\bcontests\b",
    r"(?<!no\s)\bcounter.samples?\b",
    r"\bweakens?\b",
    r"\bbreaks?\b",
    r"\bunexamined assumption\b",
    r"\bblind spot\b",
    # Specific "presents a counter-example" or "here is a counter-example"
    r"(?:here|presents|presents a|- )\s*counter[-\s]example",
    # Lines starting with "- " inside Counter-samples block
]

# Phrases indicating "no objections found" (inconclusive)
_INCONCLUSIVE_MARKERS = [
    r"\bno\s+objections?\b",
    r"\bno\s+counter.examples?\b",
    r"\bnone identified\b",
    r"\bminimal risk\b",
    r"\bnot identified\b",
]


class CrossFamilyConfigError(Exception):
    """Raised when Serge and all executors/Mona share the same provider family."""


@dataclass
class Critique:
    """Result of a ChallengerAgent.critique() call."""

    content: str
    view: str
    serge_inconclusive: bool = False
    disputed_claim_ids: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.disputed_claim_ids is None:
            self.disputed_claim_ids = []


class ChallengerAgent:
    """Serge — adversarial challenger. Cross-family, rigid 4-block output."""

    def __init__(
        self,
        armance_root: Path,
        config: Any,
        *,
        executor_families: list[str],
        mona_family: str,
        serge_family: str,
    ) -> None:
        self.armance_root = armance_root
        self.config = config
        self.serge_family = serge_family
        self._ledger = ClaimLedgerService(armance_root)

        # Hard cross-family check
        forbidden = set(executor_families) | {mona_family}
        if serge_family in forbidden:
            families = sorted(forbidden)
            raise CrossFamilyConfigError(
                f"Serge shares provider family '{serge_family}' with executors/Mona "
                f"({', '.join(families)}). "
                f"Adversarial pressure is ineffective when judge, executors, and challenger "
                f"share the same priors. Configure a second family in .armance/config.yaml "
                f"or run without --stress-test."
            )

    async def critique(
        self,
        view: str,
        target: str,
        *,
        dispute_ids: list[str] | None = None,
    ) -> Critique:
        """Critique a synthesis or step output with the rigid 4-block format.

        Steps:
        1. Build system prompt with Serge's voice + claim context from ledger.
        2. Call LLM.
        3. Downgrade disputed claims in ledger.
        4. Detect inconclusive (zero objections) → flag result.
        """
        claims = self._ledger.get_claims_by_view(view)
        
        # T-29a: Serge's enriched context reads from sqlite-vec
        # Query excluding cited chunks
        exclude_ids = []
        for c in claims:
            for e in c.evidence:
                if "rag:" in e.ref:
                    m = re.search(r"rag:(\d+)", e.ref)
                    if m:
                        exclude_ids.append(m.group(1))

        # RAG enrichment is optional: skip if index empty or unavailable
        # (avoids hitting embedding API with no corpus, e.g. in tests / fresh installs).
        extra_chunks: list = []
        try:
            rag_service = self._init_rag()
            if rag_service is not None:
                cur = rag_service.conn.cursor()
                count = cur.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
                if count > 0:
                    extra_chunks = await rag_service.query_excluding(
                        target, top_k=5, exclude_ids=exclude_ids,
                    )
        except Exception:
            logger.exception("rag enrichment skipped")

        rag_context = ""
        if extra_chunks:
            rag_lines = ["\n## Uncited RAG Evidence (Adversarial Context)"]
            for c in extra_chunks:
                rag_lines.append(f"### [rag:{c.id}] Source: {c.source}\n{c.text}")
            rag_context = "\n".join(rag_lines)

        system_prompt = self._build_system_prompt(claims, rag_context=rag_context)

        serge_agent = self._load_serge()
        client = get_client(serge_agent.provider, self.config)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                f"Critique the following synthesis for view `{view}`:\n\n{target}"
            )},
        ]

        extras: dict[str, Any] = {}
        if serge_agent.reasoning:
            extras["reasoning"] = {"effort": serge_agent.reasoning}

        response = await call_with_ledger(
            client, serge_agent.name, messages, serge_agent.model, **extras
        )

        content = response.text

        # Downgrade disputed claims
        disputed: list[str] = []
        if dispute_ids:
            for claim_id in dispute_ids:
                try:
                    from armance.core.models.claim import ClaimStatus
                    self._ledger.verify_claim(
                        claim_id,
                        verdict=ClaimStatus.DISPUTED,
                        by="system-challenger",
                        rationale="Disputed by Serge critique.",
                    )
                    disputed.append(claim_id)
                    logger.info("Serge downgraded claim %s to disputed", claim_id)
                except Exception:
                    logger.exception("Failed to downgrade claim %s", claim_id)

        # Check for inconclusive (no real objections)
        inconclusive = self._is_inconclusive(content)
        if inconclusive:
            logger.warning("Serge critique for view=%s marked serge_inconclusive", view)

        return Critique(
            content=content,
            view=view,
            serge_inconclusive=inconclusive,
            disputed_claim_ids=disputed,
        )

    def _build_system_prompt(self, claims: list, rag_context: str = "") -> str:
        cato = self._load_serge()
        base = cato.effective_system_prompt(caveman_level="none")

        if not claims and not rag_context:
            return base

        blocks = []
        if claims:
            lines = ["## Claims in ledger for this view\n"]
            for c in claims:
                evidence_note = (
                    ", ".join(e.ref for e in c.evidence) if c.evidence else "— no evidence"
                )
                lines.append(f"- `{c.id}` ({c.status.value}) by {c.by}: {c.text} [{evidence_note}]")
            blocks.append("\n".join(lines))
            
        if rag_context:
            blocks.append(rag_context)

        return base + "\n\n" + "\n\n".join(blocks)

    def _init_rag(self) -> "RagService | None":
        """Lazy init of RAG service with real embeddings from config.

        Returns None if no embedding model is configured (RAG disabled).
        """
        from armance.storage.rag_index import RagService
        from armance.service.llm_service import get_client

        provider = getattr(self.config, "embedding_provider", "")
        model = getattr(self.config, "embedding_model", "")
        if not provider or not model:
            return None
        client = get_client(provider, self.config)

        dim = 1536
        if "gemini" in provider.lower() or "gemini" in model.lower():
            dim = 768
        elif "3-large" in model:
            dim = 3072

        return RagService(
            self.armance_root,
            embedding_client=client,
            embedding_model=model,
            embedding_dim=dim
        )

    def _is_inconclusive(self, content: str) -> bool:
        """Return True if the critique contains no real objections.

        Uses two signals:
        1. Explicit "no objections" / "aucun contre-exemple" phrasing.
        2. Absence of affirmative objection phrases.
        """
        text = content.lower()
        has_inconclusive = any(re.search(pat, text) for pat in _INCONCLUSIVE_MARKERS)
        if not has_inconclusive:
            return False
        # If the Counter-samples section has only one line (the "aucun" line), inconclusive
        # Check if there's a real counter-sample (dash followed by a substantive claim)
        cs_match = re.search(
            r"##\s*counter.samples?\s*\n(.*?)(?:\n##|\Z)", text, re.DOTALL | re.IGNORECASE
        )
        if cs_match:
            cs_body = cs_match.group(1).strip()
            # Real counter-samples start with "- " and have actual content
            real_samples = [
                line for line in cs_body.splitlines()
                if line.strip().startswith("-") and len(line.strip()) > 20
                and not re.search(r"\baucun\b|\bno\b|\bnone\b", line.lower())
            ]
            if real_samples:
                return False
        return True

    def _load_serge(self):
        from armance.core.models.agent import Agent

        local = self.armance_root / "agents" / "system-challenger.md"
        if local.exists():
            return Agent.load(local)

        builtin = Path(__file__).parent / "builtin" / "system-challenger.md"
        if builtin.exists():
            return Agent.load(builtin)

        return Agent(
            name="system-challenger",
            domain="meta",
            persona="adversarial",
            provider="openrouter",
            model="openai/gpt-4o-mini",
            reasoning="medium",
            system_prompt="You are Serge, the challenger. Red-team every synthesis.",
        )
