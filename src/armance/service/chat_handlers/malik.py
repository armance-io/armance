"""Malik (system-hr) — recruiter chat shell.

Drives the user → roster dialogue. Builds the [SYSTEM CONTEXT] block with
the configured provider catalogue + tier hints so Malik never proposes
out-of-scope models, then routes through `run_specialist` for the LLM call
and intercepts `[EXECUTE:/recruit]` / `[EXECUTE:/dismiss-all]`.
"""
from __future__ import annotations

import logging
import re

from armance.nls import t
from armance.providers.model_discovery import order_models_by_effort
from armance.service.agent_sandbox import scrub_reply
from armance.service.agent_visibility import visible_turns
from armance.service.agents.specialist_runner import run_specialist
from armance.service.chat_handlers.common import resolve_agent_path, set_status
from armance.service.footprint import estimate_footprint
from armance.service.library_ops import intercept_library_status
from armance.service.loop_context import LoopContext

logger = logging.getLogger(__name__)


_KNOWN_RECRUIT_KEYS = ["name", "persona", "domain", "description", "model", "provider", "role"]
_FENCE_AGENTS_RE = re.compile(r"```(?:yaml)?\s*\n(agents:.*?)\n```", re.DOTALL)
_TOOL_CALL_RECRUIT_RE = re.compile(
    r"<tool_call>\s*execute_recruit\s*(.*?)(?:</tool_call>|$)", re.DOTALL
)


async def cmd_hr_chat(text: str, ctx: LoopContext) -> str:
    """Run one Malik turn."""
    from armance.core.models.agent import Agent
    from armance.core.models.task import Task
    from armance.service.agents.recruiter_agent import RecruiterAgentService

    agent_name = ctx.state.current_agent or "system-hr"
    set_status(ctx, agent_name, "working")

    hr_path = resolve_agent_path(ctx.armance_root, "system-hr")
    if hr_path is None:
        set_status(ctx, agent_name, "error")
        return t("meta_agent.malik_missing")
    hr_agent = Agent.load(hr_path)
    hr = RecruiterAgentService(agent=hr_agent, armance_root=ctx.armance_root, config=ctx.cfg)

    try:
        models_context = await _build_models_context(ctx)
        models_context = await _maybe_append_rag(ctx, text, models_context)

        task = Task(
            prompt=text, domain="meta", mode="light", requested_agent=agent_name,
        )
        history = visible_turns(ctx.session.conversation.turns, agent_name)
        ctx.session.conversation.append("user", text, agent=agent_name)
        hr_report = await run_specialist(
            hr_agent,
            task,
            ctx.armance_root,
            ctx.cfg,
            reports_root=ctx.armance_root / "reports",
            history=history,
            system_addon=models_context,
            event_bus=ctx.event_bus,
        )
        reply = scrub_reply(hr_report.content, agent_role="malik")
        reply = await _normalise_tier_gems(reply, ctx.cfg)
        set_status(ctx, agent_name, "completed")

        reply = _normalise_tool_call_recruit(reply)
        reply = _inject_recruit_tag_if_yaml_only(reply, text)
        reply = _handle_dismiss_all(reply, ctx)
        reply = await _handle_recruit(reply, ctx, hr)
    except Exception as exc:
        set_status(ctx, agent_name, "error")
        logger.exception("Malik LLM failed")
        reply = t("common.error", error=str(exc))

    reply = intercept_library_status(reply, ctx)
    ctx.session.conversation.append("assistant", reply, agent=agent_name)
    ctx.session.save()
    ctx._last_output = reply
    return reply


_TIER_GEM_RE = re.compile(r"[🟢🟡🟠🔴]\s*(?:free|low|medium|high)\b", re.IGNORECASE)
_ALL_GEMS = "🟢🟡🟠🔴"


async def _normalise_tier_gems(reply: str, cfg) -> str:
    """Rewrite tier gems in Malik's narrative to match the catalogue.

    Small free models routinely mis-label a model's tier (e.g. announce
    `claude-opus-4-7 🟡 low` when the discovery catalogue says
    `🔴 high`). We scan the reply for known model ids and, when one
    is followed within ~80 chars by a gem+tier blurb, replace that
    blurb with the canonical one. Lines without a matched model id are
    left untouched.
    """
    if not reply or not any(g in reply for g in _ALL_GEMS):
        return reply
    try:
        from armance.providers.discovery import discover_all
        catalogues = await discover_all(cfg)
    except Exception:
        logger.debug("tier-normalise: discovery failed", exc_info=True)
        return reply
    id_to_tier: dict[str, str] = {}
    for models in catalogues.values():
        for m in models:
            id_to_tier.setdefault(m.id, m.tier)
    if not id_to_tier:
        return reply
    # Sort longest-first so `qwen3-coder:free` doesn't match before
    # `qwen/qwen3-coder:free`.
    sorted_ids = sorted(id_to_tier.keys(), key=len, reverse=True)
    out = reply
    for mid in sorted_ids:
        canonical_tier = id_to_tier[mid]
        if not canonical_tier:
            continue
        # Replace any "gem + tier" blurb the model emitted with the plain,
        # canonical tier word — no coloured gem (DESIGN.md).
        canonical_label = canonical_tier
        pos = 0
        while True:
            idx = out.find(mid, pos)
            if idx == -1:
                break
            window_start = idx + len(mid)
            window_end = min(len(out), window_start + 80)
            window = out[window_start:window_end]
            match = _TIER_GEM_RE.search(window)
            if match:
                wstart, wend = match.span()
                out = (
                    out[: window_start + wstart]
                    + canonical_label
                    + out[window_start + wend:]
                )
            pos = idx + len(mid)
    return out


async def _resolve_tier(provider: str, model: str, cfg) -> str:
    """Look up the canonical tier for `<provider>/<model>` via discovery.

    Returns one of free/low/medium/high; falls back to 'low' if unknown so
    the roster table never carries an empty cell.
    """
    try:
        from armance.providers.discovery import discover_provider
        models = await discover_provider(provider, cfg)
        for m in models:
            if m.id == model:
                return m.tier
    except Exception:
        logger.debug("tier lookup failed for %s/%s", provider, model, exc_info=True)
    return "low"


async def _build_roster_table(created: list, cfg) -> str:
    """Render a deterministic roster table: name · provider · model · tier-gem.

    LLMs free-handing this table mis-coloured pairs at the same tier
    (e.g. opus-4-6 orange, opus-4-7 red). Generating it in Python from
    the discovery catalogue removes that drift.
    """
    if not created:
        return ""
    lines = ["", "| Agent | Provider | Model | Tier |", "|---|---|---|---|"]
    for a in created:
        tier = await _resolve_tier(a.provider, a.model, cfg)
        # Tier as a plain word — no coloured gem (DESIGN.md: no 🟢🟡🔴).
        lines.append(f"| {a.name} | {a.provider} | `{a.model}` | {tier} |")
    return "\n".join(lines)


# Representative request profile used to score models by carbon when the
# user's budget is `optimised`. 600 output tokens / 4.0s latency is a
# typical single specialist reply; absolute values don't matter — only the
# relative ordering between candidate models does.
_FOOTPRINT_TOKENS_OUT = 600
_FOOTPRINT_LATENCY_S = 4.0


def _order_for_budget(models: list, budget: str, cfg) -> list:
    """Order a provider's candidate models for the active budget tier.

    For `optimised`, sort greenest-first by estimated gCO2e using a
    `gco2e_lookup` closure over `estimate_footprint` (kept here in the
    `service` layer so the providers leaf stays import-clean). All other
    budgets return `models` unchanged — the discovery catalogue has already
    ordered them by cost.
    """
    if budget != "optimised":
        return models
    zone = getattr(getattr(cfg, "footprint", None), "electricity_mix_zone", "WOR")

    def _co2(m) -> float:
        # `m` is a ModelSpec; score its representative response.
        fp = estimate_footprint(
            m.provider,
            m.id,
            _FOOTPRINT_TOKENS_OUT,
            _FOOTPRINT_LATENCY_S,
            zone=zone,
        )
        # estimate_footprint never returns None (Task B2), but code
        # defensively: unknown → sort LAST instead of crashing.
        return fp.gco2e if fp is not None else float("inf")

    return order_models_by_effort(models, "optimised", _co2)


async def _build_models_context(ctx: LoopContext) -> str:
    """Build the [SYSTEM CONTEXT] addon injected into Malik's prompt.

    Lists model catalogues per configured provider using canonical IDs
    (e.g. `google/gemma-2-9b-it:free`, not `openrouter/google/...`). Malik
    is told to copy these IDs verbatim and never invent a provider prefix.
    """
    try:
        from armance.providers.discovery import (
            discover_all,
            filter_for_budget,
        )
    except Exception:
        logger.exception("provider discovery import failed")
        return ""

    budget = getattr(ctx.cfg, "budget_effort", "medium")
    configured = [p.name for p in (ctx.cfg.providers or [])]
    if not configured:
        configured = [getattr(ctx.cfg, "default_provider", "openrouter")]

    catalogues = await discover_all(ctx.cfg)
    if not catalogues:
        return ""

    # Some providers can't enumerate models (notably `custom-openai`, which
    # points at a user-supplied OpenAI-compatible endpoint with no canonical
    # /v1/models contract). If discovery returned an empty list but the user
    # set a default model at `armance init`, surface that one so Malik has
    # something concrete to propose instead of asking for new providers.
    default_model_id = (getattr(ctx.cfg, "default_model", "") or "").strip()
    default_provider = (getattr(ctx.cfg, "default_provider", "") or "").strip()
    if default_model_id:
        try:
            from armance.providers.base import ModelSpec
        except Exception:
            ModelSpec = None  # type: ignore[assignment]
        for prov in configured:
            if catalogues.get(prov):
                continue
            # Only seed a fallback if this provider is the user's declared
            # default (otherwise we'd advertise the same id under every
            # un-discoverable provider, which is misleading).
            if default_provider and prov != default_provider:
                continue
            if ModelSpec is None:
                continue
            # Mark as effectively_free so `filter_for_budget` never strips
            # it under a free-first budget — the user picked it on purpose.
            catalogues[prov] = [
                ModelSpec(
                    id=default_model_id,
                    provider=prov,
                    tier="low",
                    effectively_free=True,
                ),
            ]

    only = ", ".join(f"`{p}`" for p in configured)
    lines: list[str] = [
        "",
        "[SYSTEM CONTEXT]",
        f"LLM model cost budget (Armance API costs, NOT the user's project budget): {budget.upper()}.",
        f"CONFIGURED PROVIDERS (the user has access to ONLY these): {only}.",
        "Do NOT pretend other providers are available. Do NOT prefix the model "
        "id with the provider name — the YAML's `provider:` field already "
        "carries that. `provider:` must be exactly one of the names above "
        "(`openrouter`, `gemini`, `claude-code`, `custom-openai`).",
    ]
    for prov in configured:
        models = filter_for_budget(catalogues.get(prov, []), budget)
        if not models:
            lines.append(f"\nProvider `{prov}`: (no models discovered)")
            continue
        # `optimised` budget: order the whole provider list greenest-first by
        # estimated carbon, crossing tier boundaries. Other budgets keep the
        # cost-ordered, tier-grouped view below.
        models = _order_for_budget(models, budget, ctx.cfg)
        lines.append(f"\nProvider `{prov}`:")
        if budget == "optimised":
            ids = [m.id for m in models]
            shown = ids if len(ids) <= 50 else ids[:50]
            suffix = f" (+{len(ids) - 50} more)" if len(ids) > 50 else ""
            lines.append(
                f"  - greenest first (lowest estimated gCO2e): "
                f"{', '.join(shown)}{suffix}"
            )
        else:
            by_tier: dict[str, list[str]] = {"free": [], "low": [], "medium": [], "high": []}
            for m in models:
                by_tier[m.tier].append(m.id)
            for tier in ("free", "low", "medium", "high"):
                ids = by_tier[tier]
                if not ids:
                    continue
                # Cap only at very large counts (50+) to keep the prompt sane.
                # Otherwise list ALL available models so Malik sees the full
                # menu — users complained they were only offered a fraction.
                shown = ids if len(ids) <= 50 else ids[:50]
                suffix = f" (+{len(ids) - 50} more)" if len(ids) > 50 else ""
                lines.append(f"  - {tier}: {', '.join(shown)}{suffix}")
        reasoning_ids = [m.id for m in models if m.supports_reasoning][:8]
        if reasoning_ids:
            lines.append(f"  - Reasoning-effort supported: {', '.join(reasoning_ids)}")
        else:
            lines.append(
                "  - Reasoning-effort: none of the listed models accept "
                "a `reasoning:` field (do NOT add one)"
            )
        # Web-search capable models (Perplexity Sonar, OpenRouter `:online`,
        # Gemini grounding, Claude WebSearch tool). Mark which are
        # effectively-free for the user (subscription or :free).
        search_models = [m for m in models if m.supports_search]
        if search_models:
            lines.append("  - 🔍 Web-search capable:")
            for m in search_models[:12]:
                marker = "🎁 effectively free" if m.effectively_free else m.tier
                lines.append(f"      - {m.id} ({marker})")
        else:
            lines.append("  - 🔍 Web-search capable: none")

    lines.append("")
    lines.append(
        "STRICT YAML CONTRACT for [EXECUTE:/recruit]:\n"
        "  - `provider:` = one of the names above, NOTHING ELSE.\n"
        "  - `model:` = a canonical id copied verbatim from the lists above. "
        "  - Add `reasoning: low|medium|high` only if the model is in the "
        "reasoning-supported list for its provider.\n"
        "Show each agent in your plan as '<provider> / <model>' with the "
        "tier gem from the lists. Any agent whose model id is NOT in the "
        "catalogue will be rejected by the validator."
    )
    lines.append("")
    lines.append(
        "GROUNDING POLICY — fact-heavy roles need web search:\n"
        "  Fact-heavy = roles whose answers depend on real-world facts "
        "(historien, journaliste, juriste, médecin, fact-checker, "
        "researcher, ...), OR any role in a workflow whose scope mentions "
        "sourced / vérifié / fact-checked / archives / cited / dossier "
        "rigoureux. For these roles, ALWAYS prefer a 🔍 search-capable "
        "model over a non-search free one — even if the search model is "
        "in a higher tier — because free non-search models hallucinate "
        "dates, names, and citations.\n"
        "  Priority order under `free-first` budget:\n"
        "    1. 🎁 effectively-free search models (Claude Haiku via "
        "subscription, Gemini Flash if low cost is acceptable to the user).\n"
        "    2. Paid search models (Perplexity Sonar) — ask the user.\n"
        "    3. Free non-search models (LAST resort; warn the user "
        "outputs may be hallucinated).\n"
        "  For non-fact-heavy roles (organisateur, communicant, "
        "facilitateur, brainstormer), stick to the cheapest free option."
    )
    return "\n".join(lines)


async def _maybe_append_rag(ctx: LoopContext, text: str, base: str) -> str:
    try:
        from armance.service.agents._rag_inject import inject_rag_section
        rag_section = await inject_rag_section(ctx.armance_root, text, k=3, config=ctx.cfg)
        if rag_section:
            return (base + "\n\n" + rag_section).strip()
    except Exception:
        logger.debug("RAG injection skipped for Malik", exc_info=True)
    return base


def _normalise_tool_call_recruit(reply: str) -> str:
    """Convert `<tool_call>execute_recruit ...` → `[EXECUTE:/recruit]` + YAML."""
    if "<tool_call>" not in reply or "execute_recruit" not in reply:
        return reply
    if "[EXECUTE:/recruit]" in reply:
        return reply
    tc_match = _TOOL_CALL_RECRUIT_RE.search(reply)
    if not tc_match:
        return reply
    kv_text = tc_match.group(1).strip().lstrip("•- ")
    kv_pairs = _parse_inline_kv(kv_text)
    if not kv_pairs:
        kv_pairs = _parse_line_kv(kv_text)
    if "name" not in kv_pairs:
        return reply
    yaml_lines = ["agents:"]
    first = True
    for key, val in kv_pairs.items():
        prefix = "  - " if first else "    "
        yaml_lines.append(f"{prefix}{key}: {val}")
        first = False
    synthetic = "\n".join(yaml_lines)
    pre = reply[: reply.find("<tool_call>")].strip()
    return f"{pre}\n[EXECUTE:/recruit]\n{synthetic}"


def _parse_inline_kv(kv_text: str) -> dict[str, str]:
    pattern = r"\b(" + "|".join(_KNOWN_RECRUIT_KEYS) + r")\s*:\s*"
    parts = re.split(pattern, kv_text)
    pairs: dict[str, str] = {}
    it = iter(parts[1:])
    for key in it:
        val = next(it, "").strip().rstrip(" •")
        pairs[key.strip()] = val
    return pairs


def _parse_line_kv(kv_text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for line in kv_text.splitlines():
        line = line.strip().lstrip("•- ")
        if ":" in line:
            k, _, v = line.partition(":")
            pairs[k.strip()] = v.strip()
    return pairs


_USER_RECRUIT_INTENTS = (
    "recrute", "complete", "complète", "go", "vas-y", "vas y", "lance",
    "recommence", "rebuild", "redo", "recruit", "do it", "fais le", "fais-le",
)


def _inject_recruit_tag_if_yaml_only(reply: str, user_text: str) -> str:
    """Safety net: weak free models often emit an `agents:` YAML block without
    `[EXECUTE:/recruit]`, leaving the user staring at raw YAML and nothing
    happening. If the user clearly asked for recruitment AND the reply
    contains a valid-looking `agents:` block but no recruit tag, inject one.
    """
    if "[EXECUTE:/recruit]" in reply:
        return reply
    if not _FENCE_AGENTS_RE.search(reply) and "agents:" not in reply:
        return reply
    low = (user_text or "").lower().strip()
    if not any(intent in low for intent in _USER_RECRUIT_INTENTS):
        return reply
    logger.warning("Malik emitted agents YAML without [EXECUTE:/recruit]; injecting tag")
    # Place the tag immediately before the YAML block so _handle_recruit
    # picks it up cleanly.
    fence = _FENCE_AGENTS_RE.search(reply)
    if fence:
        start = fence.start()
        return reply[:start].rstrip() + "\n\n[EXECUTE:/recruit]\n" + reply[start:]
    idx = reply.find("agents:")
    return reply[:idx].rstrip() + "\n\n[EXECUTE:/recruit]\n" + reply[idx:]


async def _emit_agents_proposed(ctx: LoopContext, created: list) -> None:
    """C.6 — emit `agents_proposed` event on the web event bus.

    No-op when ctx.event_bus is None (TUI path).  The payload carries
    the contract fields the frontend needs to render the panel cards:
    name, role, persona label, description, provider, model, reasoning.
    """
    bus = getattr(ctx, "event_bus", None)
    if bus is None or not created:
        return
    payload: list[dict[str, object]] = []
    for a in created:
        persona_label = ""
        if getattr(a, "persona", None) is not None:
            persona_label = getattr(a.persona, "label", "") or ""
        payload.append({
            "name": a.name,
            "role": (a.role or a.domain or "specialist"),
            "persona": persona_label,
            "description": getattr(a, "description", "") or "",
            "provider": a.provider,
            "model": a.model,
            "reasoning": a.reasoning,
        })
    try:
        # Event names must be dotted (<component>.<action>) — the bus rejects
        # underscored names, which silently dropped the recruit refresh.
        await bus.emit("agents.proposed", attributes={"agents": payload})
    except Exception:
        logger.exception("event_bus.emit(agents.proposed) failed")


def _peek_proposed_names(yaml_text: str) -> list[str]:
    """Extract `name:` values from the recruit YAML without full parsing.

    Cheap regex scan — we only need to count and de-dup. Returns names in
    appearance order.
    """
    names: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"^\s*-?\s*name\s*:\s*([A-Za-z0-9_.\- ]+)\s*$", yaml_text, re.MULTILINE):
        n = m.group(1).strip()
        if n and n not in seen:
            names.append(n)
            seen.add(n)
    return names


def _auto_dismiss_specialists(ctx: LoopContext, agents_dir) -> None:
    """Delete every specialist .md (keep system-*/_-prefixed assets) and
    prune the registry. Mirrors the body of [EXECUTE:/dismiss-all] without
    the surrounding LLM reply plumbing."""
    if agents_dir.exists():
        for p in list(agents_dir.glob("*.md")):
            if p.stem.startswith(("system-", "_")):
                continue
            try:
                p.unlink()
            except Exception:
                logger.exception("auto-dismiss: failed to delete %s", p)
    try:
        from armance.storage import paths
        registry = paths.ensure_agents_registry(ctx.armance_root)
        live_stems = {p.stem for p in agents_dir.glob("*.md")} if agents_dir.exists() else set()
        registry["agents"] = [
            a for a in registry.get("agents", [])
            if a.get("name") in live_stems or str(a.get("name", "")).startswith("system-")
        ]
        paths.write_agents_registry(ctx.armance_root, registry)
    except Exception:
        logger.exception("auto-dismiss: registry prune failed")
    ctx.agents = [a for a in ctx.agents if a.name.startswith("system-")]


def _handle_dismiss_all(reply: str, ctx: LoopContext) -> str:
    if "[EXECUTE:/dismiss-all]" not in reply:
        return reply
    reply = reply.replace("[EXECUTE:/dismiss-all]", "").strip()
    agents_dir = ctx.armance_root / "agents"
    deleted: list[str] = []
    if agents_dir.exists():
        for p in list(agents_dir.glob("*.md")):
            # Skip system-* (meta-agents) AND underscore-prefixed assets
            # (e.g. `_armance_concepts`, internal docs surfaced as agent files).
            if p.stem.startswith(("system-", "_")):
                continue
            try:
                p.unlink()
                deleted.append(p.stem)
            except Exception:
                logger.exception("dismiss-all: failed to delete %s", p)
    # Drop the same agents from the registry so the sidebar / loader stay in sync.
    # Anything not present in agents_dir is also pruned (catches rogue staff-
    # named registry entries from older versions of the recruit path).
    try:
        from armance.storage import paths
        registry = paths.ensure_agents_registry(ctx.armance_root)
        live_stems = {p.stem for p in agents_dir.glob("*.md")} if agents_dir.exists() else set()
        before = len(registry.get("agents", []))
        registry["agents"] = [
            a for a in registry.get("agents", [])
            if a.get("name") in live_stems or str(a.get("name", "")).startswith("system-")
        ]
        if len(registry["agents"]) != before:
            paths.write_agents_registry(ctx.armance_root, registry)
    except Exception:
        logger.exception("dismiss-all: registry prune failed")
    ctx.agents = [a for a in ctx.agents if a.name.startswith("system-")]
    if deleted:
        reply += "\n\n" + t("system_msg.dismissed", n=len(deleted), names=", ".join(deleted))
    else:
        reply += "\n\n" + t("system_msg.dismiss_empty")
    return reply


async def _handle_recruit(reply: str, ctx: LoopContext, hr) -> str:
    if "[EXECUTE:/recruit]" not in reply:
        return reply
    full_reply = reply
    reply = reply.replace("[EXECUTE:/recruit]", "").strip()

    yaml_part = ""
    fence_match = _FENCE_AGENTS_RE.search(full_reply)
    if fence_match:
        yaml_part = fence_match.group(0)
        reply = reply.replace(yaml_part, "").strip()
    else:
        idx = full_reply.find("agents:")
        if idx != -1:
            yaml_part = full_reply[idx:]
            reply = reply[: reply.find("agents:")].strip()
    if not yaml_part:
        _, yaml_part = full_reply.split("[EXECUTE:/recruit]", 1)

    try:
        agents_dir = ctx.armance_root / "agents"

        # Guard against accidental double-recruitment: if Malik proposes a
        # full new roster (>=3 agents, none share a name with currently
        # recruited specialists), dismiss existing specialists first.
        # Without this, the team silently grows from 8 to 16 because
        # recruit_agents only matches on name.
        proposed = _peek_proposed_names(yaml_part)
        current_specialists = [
            a.name for a in ctx.agents
            if not a.name.startswith("system-") and not a.name.startswith("_")
        ]
        if (
            len(proposed) >= 3
            and current_specialists
            and not (set(proposed) & set(current_specialists))
        ):
            logger.info(
                "Malik full-roster reshuffle detected; auto-dismissing %d "
                "existing specialists before recruit",
                len(current_specialists),
            )
            _auto_dismiss_specialists(ctx, agents_dir)
            reply += "\n\n" + t(
                "system_msg.auto_dismissed_before_recruit",
                n=len(current_specialists),
            )

        created, created_names = hr.recruit_agents(
            yaml_text=yaml_part,
            role_name="specialist",
            agents_dir=agents_dir,
        )
        for a in created:
            idx_match = next(
                (i for i, x in enumerate(ctx.agents) if x.name == a.name), None,
            )
            if idx_match is not None:
                ctx.agents[idx_match] = a
            else:
                ctx.agents.append(a)

        # C.6: emit `agents_proposed` so the web frontend can render
        # the recruitment panel cards. No-op in the TUI (no event_bus).
        await _emit_agents_proposed(ctx, created)

        # Second pass: ask the LLM to write a rich persona-grade system
        # prompt for each newly-created agent and persist it into the .md.
        # Fans out in parallel; one call per agent. If it fails, the
        # minimal frontmatter-only .md stays — the agent still works,
        # just sounds generic.
        if created:
            try:
                from armance.service.agents.persona_writer import write_personas
                await write_personas(
                    created,
                    ctx.state.project_brief or "",
                    ctx.armance_root,
                    ctx.cfg,
                )
                # Reload the agents from disk so the in-memory list carries
                # the freshly-written system_prompt.
                from armance.core.models.agent import Agent
                for a in created:
                    path = ctx.armance_root / "agents" / f"{a.name}.md"
                    if path.exists():
                        reloaded = Agent.load(path)
                        for i, x in enumerate(ctx.agents):
                            if x.name == reloaded.name:
                                ctx.agents[i] = reloaded
                                break
            except Exception:
                logger.exception("persona-writer pass failed")

        # Feedback on recruitment telemetry
        new_names = getattr(hr, "last_new_names", [])
        if new_names:
            reply += "\n\n" + t("system_msg.recruited", n=len(new_names))
            try:
                roster = await _build_roster_table(created, ctx.cfg)
                if roster:
                    reply += "\n" + roster
            except Exception:
                logger.debug("roster table build failed", exc_info=True)

        updated_names = getattr(hr, "last_updated_names", [])
        if updated_names:
            reply += "\n\n" + t("system_msg.updated", n=len(updated_names), names=", ".join(updated_names))

        staff_updates = getattr(hr, "last_staff_updates", [])
        if staff_updates:
            reply += "\n\n" + t("system_msg.staff_updated", n=len(staff_updates), details=", ".join(staff_updates))

        skipped_collisions = getattr(hr, "last_skipped_collisions", [])
        if skipped_collisions:
            reply += "\n\n" + t("system_msg.skipped_collision", n=len(skipped_collisions), names=", ".join(skipped_collisions))

        # Third pass: health-check each recruited agent. Persist the result
        # on disk and surface failures so the user can pick another model
        # before relying on the team.
        if created:
            try:
                from armance.service.agents.health import (
                    check_many,
                    persist_health,
                )
                results = await check_many(created, ctx.cfg)
                agents_dir = ctx.armance_root / "agents"
                bad: list[str] = []
                for r in results:
                    persist_health(r, agents_dir)
                    if not r.ok:
                        bad.append(f"`{r.agent}` ({r.status})")
                if bad:
                    reply += (
                        "\n\n"
                        + t("system_msg.health_warning", agents=", ".join(bad))
                    )
            except Exception:
                logger.exception("post-recruit health-check failed")
    except Exception as e:
        logger.exception("Failed to recruit agents")
        reply += "\n\n" + t("system_msg.recruit_failed", error=str(e))
    return reply
