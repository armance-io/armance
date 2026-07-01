"""SpecialistRunner — run a single specialist agent with L0 + L1[role] context.

Implements T-15d: L1 per-role dialogue (no RAG).
Before building the system prompt, loads L0 body + L1[role] body
via ContextService and appends them to the agent's system prompt.

T-15f: After LLM response, parses claim blocks and emits them to the
claim ledger via ClaimLedgerService.

Spec refs: 05_context.md (Layered loading at LLM call time),
19_claim_ledger.md (Path A — Inline annotation)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from armance.core.models.agent import Agent
from armance.core.models.task import Task
from armance.service.claim_ledger_service import ClaimLedgerService
from armance.service.claim_parser import parse_claims
from armance.service.context_service import ContextService
from armance.service.llm_service import call_with_ledger, get_client
from armance.service.report import Report, write_report

logger = logging.getLogger(__name__)


class SpecialistRunner:
    """Runs a single specialist agent with layered context (L0 + L1[role])."""

    def __init__(
        self,
        armance_root: Path,
        config: Any,
        reports_root: Path | None = None,
    ) -> None:
        self.armance_root = armance_root
        self.config = config
        self.reports_root = reports_root or (armance_root / "reports")
        self.context_service = ContextService(armance_root)
        self._claim_ledger: ClaimLedgerService | None = None

    async def run(
        self,
        agent: Agent,
        task: Task,
        *,
        history: list[dict[str, str]] | None = None,
        on_token: Callable[[str], None] | None = None,
        view: str = "open-space",
        caveman_level: str = "none",
        system_addon: str | None = None,
        event_bus: Any | None = None,
        boosted_agents: set[str] | None = None,
    ) -> Report:
        """Run a single specialist agent with L0 + L1[role] context.

        The system prompt is built as:
            caveman_protocol + agent.system_prompt + L0_body + L1[role]_body
        """
        from armance.service.boost_ops import boosted_model_for
        eff_provider, eff_model = boosted_model_for(agent, boosted_agents or set())
        client = get_client(eff_provider, self.config)

        # Build layered context
        context = self._build_layered_context(agent)

        # T-27: RAG enrichment (retrieve evidence based on the current task prompt)
        context = await self.context_service.enrich_for_agent(
            agent.name, context, task.prompt
        )

        # Persistent "read" docs: any specialist sees the full text of docs
        # the user marked /library load --persist. Session-only "read" docs
        # are scoped to the host agent and not injected here (they'd require
        # a session ref this runner does not carry).
        try:
            from armance.storage.library_state import load_persistent_read
            read_files = load_persistent_read(self.armance_root)
            if read_files:
                docs_dir = self.armance_root / "docs"
                blocks: list[str] = []
                for name in sorted(read_files):
                    f = docs_dir / name
                    if not f.exists():
                        continue
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    if text.strip():
                        blocks.append(f"### `{name}`\n{text[:6000]}")
                if blocks:
                    context = (
                        (context + "\n\n" if context else "")
                        + "## Loaded documents (read by every agent)\n\n"
                        + "\n\n".join(blocks)
                    )
        except Exception:
            logger.debug("read-doc inject skipped", exc_info=True)

        system_prompt = agent.effective_system_prompt(caveman_level=caveman_level)

        if caveman_level == "none":
            # Positive instruction only. Naming the compression style here makes
            # weak models echo the label ("Caveman pause — …") into the human
            # turn, so we describe the *desired* register without mentioning it.
            system_prompt += (
                "\n\n## Communication Style — Direct Human Dialogue\n"
                "You are in direct, personal dialogue with the human user (CEO). "
                "Reply in a natural, polite, fully-articulated style with complete "
                "sentences and proper grammar. Never narrate your own response style "
                "or formatting; just speak."
            )

        # Sandbox reminder for non-meta specialists: no tools available.
        # The defense layer strips any [EXECUTE:/...] tag anyway, but
        # telling the model up-front saves tokens and avoids confused
        # replies where the agent claims to have done something.
        if not agent.name.startswith("system-"):
            system_prompt += (
                "\n\n## Sandbox\nYou are a specialist agent. You have NO tools — "
                "no `[EXECUTE:/...]` tag will fire if you emit one (they are stripped). "
                "If you need recruitment, mention `@Malik`. If you need a workflow, "
                "mention `@Kim`. If new project context is needed, suggest the user "
                "ask `@Armance` to save it. Never emit `<tool_call>` markup."
            )
            system_prompt += (
                "\n\n## STRICT NON-HALLUCINATION & ANTI-HYPOTHESIS POLICY\n"
                "Do NOT speculate, guess, or invent missing information or facts. If you lack "
                "data, files, or critical elements required to answer a question or make a decision, "
                "you MUST explicitly flag this in your deliverable output by stating:\n"
                "- `QUESTION: <the specific question or information needed>`\n"
                "- `HYPOTHESIS: <the explicitly stated hypothesis you are making to proceed, and why>`\n"
                "Be extremely transparent. Do not invent context or make silent assumptions."
            )

        if system_addon:
            system_prompt = f"{system_prompt}\n\n{system_addon}"
        if context:
            system_prompt = f"{system_prompt}\n\n--- Context ---\n{context}"

        # Voice overlay LAST — weak models follow the final instruction best.
        try:
            from armance.service.agents._voice_overlay import voice_overlay
            system_prompt = f"{system_prompt}\n\n{voice_overlay(getattr(self.config, 'language', 'en'))}"
        except Exception:
            pass

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": task.prompt})

        extras: dict[str, Any] = {}
        if agent.reasoning:
            extras["reasoning"] = {"effort": agent.reasoning}

        # Web-search activation. Look up the agent's model in the provider
        # catalogue cache. If the spec advertises grounding, adapt the
        # request per its search_mode:
        #   - "suffix": append `:online` to the model id (OpenRouter).
        #   - "tool":   inject the provider-specific search tool param.
        #   - "builtin": nothing to do (model already searches).
        effective_model = eff_model
        try:
            from armance.providers.discovery import _CACHE as _DISCOVERY_CACHE
            spec = next(
                (
                    m for m in _DISCOVERY_CACHE.get(eff_provider, [])
                    if m.id == eff_model
                ),
                None,
            )
            if spec is not None and spec.supports_search:
                if spec.search_mode == "suffix" and not eff_model.endswith(":online"):
                    effective_model = f"{eff_model}:online"
                elif spec.search_mode == "tool":
                    extras.setdefault("tools", []).append(
                        _search_tool_for(eff_provider),
                    )
        except Exception:
            logger.debug("search activation lookup failed", exc_info=True)

        # C.8 — bridge token-stream callbacks to agent_streaming_* events
        # when an event_bus is wired (web client). No-op in the TUI.
        from armance.service.agents._streaming_bridge import (
            AgentStreamingEmitter,
            bridge_on_token,
        )
        emitter = AgentStreamingEmitter(bus=event_bus, agent_name=agent.name)
        await emitter.start()
        effective_on_token = bridge_on_token(original=on_token, emitter=emitter)

        try:
            response = await call_with_ledger(
                client,
                agent.name,
                messages,
                effective_model,
                on_token=effective_on_token,
                provider=eff_provider,
                **extras
            )
        finally:
            await emitter.end()

        report = Report.from_completion(
            agent_name=agent.name,
            role=task.role,
            prompt=task.prompt,
            content=response.text,
            finish_reason=response.finish_reason,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=response.cost_usd,
        )

        # T-15f: Parse claims and emit to ledger with correct view
        self._emit_claims(report.content, agent.name, view)

        return report

    def _build_layered_context(self, agent: Agent) -> str:
        """Build L0 + L1[role] context string for prompt injection.

        Per spec §05_context.md — Layered loading at LLM call time:
            final_prompt = (
                caveman_protocol +
                agent.system_prompt +
                L0_body +
                cache_body (shared pending notes) +
                (L1[agent.role] if exists) +
                ...
            )
        """
        parts: list[str] = []

        # L0: always loaded
        l0_body = self.context_service.read_l0_body()
        if l0_body:
            parts.append(f"## L0 — Project Context\n\n{l0_body}")

        # Shared incremental brief: pending cache notes (Armance-owned).
        cache_body = self.context_service.read_cache()
        if cache_body:
            parts.append(f"## Shared notes (pending context)\n\n{cache_body}")

        # L1: per-role, only if agent has a role and L1 exists
        role = agent.role
        if role:
            l1_body = self.context_service.read_current_l1(role)
            if l1_body:
                parts.append(f"## L1 — {role} Context\n\n{l1_body}")

        # L2: per-theme (the agent's role), if exists
        if role:
            l2_body = self.context_service.read_current_l2(role)
            if l2_body:
                parts.append(f"## L2 — {role} Topic Knowledge\n\n{l2_body}")

        # Team roster: every agent must know the whole team — who else is on
        # board, their role, and (for same-role peers) the distinct angle each
        # holds, so they can build on / push against the right colleagues.
        from armance.service.agents._team_roster import build_team_roster
        # Malik (the recruiter) needs the health markers so it knows which
        # agents to repair with /agent-swap; specialists get the lean view.
        show_health = agent.name == "system-hr"
        roster = build_team_roster(
            self.armance_root, agent.name, show_health=show_health
        )
        if roster:
            parts.append(roster)

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Claim emission (T-15f)
    # ------------------------------------------------------------------

    @property
    def claim_ledger(self) -> ClaimLedgerService:
        """Lazy-initialize the claim ledger service."""
        if self._claim_ledger is None:
            self._claim_ledger = ClaimLedgerService(self.armance_root)
        return self._claim_ledger

    def _emit_claims(
        self,
        content: str,
        agent_name: str,
        view: str,
    ) -> None:
        """Parse claims from L1 output and emit them to the ledger.

        Called after the LLM response is complete.  Parses ``[[claim ...]]``
        blocks from the response text and appends each to the claim ledger.

        Args:
            content: The LLM response text (deliverable).
            agent_name: Canonical agent name for the ``by`` field.
            view: ViewRef where the claim was made.
        """
        try:
            claims = parse_claims(content, defaults={"by": agent_name, "view": view})
        except Exception:
            logger.exception("Claim parsing failed, continuing without claims")
            return

        if not claims:
            return

        ledger = self.claim_ledger
        for claim in claims:
            try:
                ledger.append_claim(claim)
                logger.info("Emitted claim %s by %s", claim.id, claim.by)
            except Exception:
                logger.exception("Failed to append claim %s to ledger", claim.id)

        logger.info("Emitted %d claims from %s output", len(claims), agent_name)


_SEARCH_TOOL_BY_PROVIDER: dict[str, dict[str, Any]] = {
    # Google Gemini exposes the built-in search tool via `google_search`.
    "gemini": {"google_search": {}},
    # Claude SDK exposes WebSearch via tool name.
    "claude-code": {"name": "web_search"},
}


def _search_tool_for(provider: str) -> dict[str, Any]:
    """Return the provider-specific tool descriptor for native web search.

    Concrete providers are expected to pass this dict through verbatim in
    their request payload. Unknown providers get an empty dict — the
    caller can short-circuit on truthiness.
    """
    return _SEARCH_TOOL_BY_PROVIDER.get(provider, {})


async def run_specialist(
    agent: Agent,
    task: Task,
    armance_root: Path,
    config: Any,
    *,
    reports_root: Path | None = None,
    history: list[dict[str, str]] | None = None,
    on_token: Callable[[str], None] | None = None,
    view: str = "open-space",
    caveman_level: str = "none",
    system_addon: str | None = None,
    event_bus: Any | None = None,
    boosted_agents: set[str] | None = None,
) -> Report:
    """Convenience function to run a single specialist agent."""
    runner = SpecialistRunner(armance_root, config, reports_root=reports_root)
    report = await runner.run(
        agent, task,
        history=history,
        on_token=on_token,
        view=view,
        caveman_level=caveman_level,
        system_addon=system_addon,
        event_bus=event_bus,
        boosted_agents=boosted_agents,
    )
    write_report(report, runner.reports_root)
    return report
