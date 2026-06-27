"""/save command handlers — extracted from service/handlers.py.

Three layers:
  - L0 — project-level brief (frozen by Armance via HostAgentService.freeze)
  - L1 — per-role context (SetL1Skill)
  - L2 — per-theme context (SetL2Skill)

Routing key: `--layer=L0` (default) / `--layer=L1` / `--layer=L2`.
"""
from __future__ import annotations

import logging
import re

from armance.nls import t
from armance.service.loop_context import LoopContext

logger = logging.getLogger(__name__)


async def cmd_save(args: list[str], ctx: LoopContext) -> str:
    """Save / freeze context to L0 (default) or L1/L2 (--layer=L1|L2)."""
    args_str = " ".join(args)

    if "--layer=L1" in args or "--layer=l1" in args:
        return _save_l1(args_str, ctx)
    if "--layer=L2" in args or "--layer=l2" in args:
        return _save_l2(args_str, ctx)

    # Validate buffer content: minimum 30 non-greeting characters.
    # freeze() consumes the on-disk cache first, so the brevity guard must
    # measure the same source (cache, falling back to the in-memory buffer).
    buffer_list = list(ctx.session.metadata.get("host_buffer", []))
    from armance.service.context_service import ContextService
    full_text = ContextService(ctx.armance_root).read_cache() or "\n".join(buffer_list)
    cleaned = full_text.lower()
    for greeting in [
        "hello", "hi", "hey", "yo", "bonjour", "salut", "coucou",
        "merci", "thanks", "s'il te plaît", "please", "s'il vous plaît", "svp",
    ]:
        cleaned = re.sub(r"\b" + re.escape(greeting) + r"\b", "", cleaned)
    alphanum = "".join(c for c in cleaned if c.isalnum())
    if len(alphanum) < 30:
        return t("save.too_brief")

    try:
        from armance.core.models.agent import Agent

        context_agent_path = ctx.armance_root / "agents" / "system-context.md"
        if not context_agent_path.exists():
            from armance import paths
            context_agent_path = paths.global_agents_dir() / "system-context.md"
        if not context_agent_path.exists():
            return t("meta_agent.armance_missing")
        context_agent = Agent.load(context_agent_path)

        from armance.service.agents.host_agent import HostAgentService
        cas = HostAgentService(
            agent=context_agent,
            armance_root=ctx.armance_root,
            config=ctx.cfg,
        )
        cas._buffer = list(buffer_list)
        version = await cas.freeze()
        ctx.session.metadata["host_buffer"] = []
        ctx.session.save()
        return t("save.saved", version=f"{version.version:03d}")
    except Exception as exc:
        logger.exception("save failed")
        return t("save.error", error=str(exc))


def _save_l1(args_str: str, ctx: LoopContext) -> str:
    """Write L1 per-role context via SetL1Skill."""
    from armance.service.skills.set_l1 import SetL1Skill

    skill = SetL1Skill(armance_root=ctx.armance_root, config=ctx.cfg)
    buffer_list = list(ctx.session.metadata.get("host_buffer", []))
    for fact in buffer_list:
        skill.add_to_buffer(fact)

    role_match = re.search(r"--role=(\S+)", args_str)
    if role_match:
        skill.set_role(role_match.group(1).lower())
    elif ctx.state.current_agent:
        from armance.service.tui_bridge import find_agent_by_name
        agent = find_agent_by_name(ctx.agents, ctx.state.current_agent)
        if agent:
            skill.set_role(agent.role or ctx.state.current_agent)

    result = skill.run(args=args_str, ctx=None)
    if "error" not in result.lower():
        ctx.session.metadata["host_buffer"] = []
        ctx.session.save()
    return result


def _save_l2(args_str: str, ctx: LoopContext) -> str:
    """Write L2 per-theme context via SetL2Skill."""
    from armance.service.skills.set_l2 import SetL2Skill

    skill = SetL2Skill(armance_root=ctx.armance_root, config=ctx.cfg)
    buffer_list = list(ctx.session.metadata.get("host_buffer", []))
    for fact in buffer_list:
        skill.add_to_buffer(fact)

    theme_match = re.search(r"--theme=(\S+)", args_str)
    if theme_match:
        skill.set_theme(theme_match.group(1).lower())
    elif ctx.state.current_agent:
        from armance.service.tui_bridge import find_agent_by_name
        agent = find_agent_by_name(ctx.agents, ctx.state.current_agent)
        if agent:
            skill.set_theme(agent.role or ctx.state.current_agent)

    result = skill.run(args=args_str, ctx=None)
    if "error" not in result.lower():
        ctx.session.metadata["host_buffer"] = []
        ctx.session.save()
    return result
