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
from armance.service.agent_sandbox import scrub_reply
from armance.service.agents.specialist_runner import run_specialist
from armance.service.chat_handlers.common import resolve_agent_path, set_status
from armance.service.library_ops import intercept_library_status
from armance.service.loop_context import LoopContext

logger = logging.getLogger(__name__)


_MALIK_AGENTS = {"system-hr", "malik"}
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
        history = _filter_history(ctx, agent_name)
        ctx.session.conversation.append("user", text, agent=agent_name)
        hr_report = await run_specialist(
            hr_agent,
            task,
            ctx.armance_root,
            ctx.cfg,
            reports_root=ctx.armance_root / "reports",
            history=history,
            system_addon=models_context,
        )
        reply = scrub_reply(hr_report.content, agent_role="malik")
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


def _filter_history(ctx: LoopContext, agent_name: str) -> list[dict[str, str]]:
    """Keep only Malik-relevant turns to prevent cross-agent persona bleed."""
    out: list[dict[str, str]] = []
    for turn in ctx.session.conversation.turns:
        norm = (turn.agent or "").lower().replace("system-", "")
        if turn.role == "user" or norm in _MALIK_AGENTS or turn.agent == agent_name:
            out.append({"role": turn.role, "content": turn.content})
    return out


_TIER_GEMS = {"free": "🟢", "low": "🟡", "medium": "🟠", "high": "🔴"}


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
        by_tier: dict[str, list[str]] = {"free": [], "low": [], "medium": [], "high": []}
        for m in models:
            by_tier[m.tier].append(m.id)
        lines.append(f"\nProvider `{prov}`:")
        for tier in ("free", "low", "medium", "high"):
            ids = by_tier[tier]
            if not ids:
                continue
            gem = _TIER_GEMS[tier]
            # Cap only at very large counts (50+) to keep the prompt sane.
            # Otherwise list ALL available models so Malik sees the full
            # menu — users complained they were only offered a fraction.
            shown = ids if len(ids) <= 50 else ids[:50]
            suffix = f" (+{len(ids) - 50} more)" if len(ids) > 50 else ""
            lines.append(f"  - {gem} {tier}: {', '.join(shown)}{suffix}")
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
