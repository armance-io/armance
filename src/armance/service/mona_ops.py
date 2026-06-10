"""Mona chat shell + side-effect tags ([save-deliverable], [load-run]).

Mona is the only meta-agent that engages with project *content*. His
tags let the user persist a synthesis into the library or pull past
workflow runs back into the conversation for comparison.

Tag contracts:
  [EXECUTE:/save-deliverable:<basename>]
    Saves Mona's most recent reply into
    .armance/docs/mona-<basename>-<ts>.md so the user can /library index
    it later. <basename> sanitised to [\\w-].

  [EXECUTE:/load-run:<workflow>:<run_id>]
    Loads every file from .armance/exports/<workflow>/<run_id>/ into
    Mona's next-turn raw context. Also available to specialists for
    comparison work. <workflow> and <run_id> must match an existing run.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from armance.nls import t
from armance.service.agent_sandbox import scrub_reply
from armance.service.loop_context import LoopContext

logger = logging.getLogger(__name__)


_SAVE_TAG = re.compile(r"\[EXECUTE:/save-deliverable:([^\]]+)\]")
_LOAD_TAG = re.compile(r"\[EXECUTE:/load-run:([^:]+):([^\]]+)\]")


async def cmd_mona_chat(text: str, ctx: LoopContext) -> str:
    """Mona — synthesis chat with /save-deliverable + /load-run."""
    from armance.core.models.agent import Agent
    from armance.service.agents.host_agent import HostAgentService

    agent_name = "system-judge"
    mona_path = ctx.armance_root / "agents" / f"{agent_name}.md"
    if not mona_path.exists():
        from armance import paths
        mona_path = paths.global_agents_dir() / f"{agent_name}.md"
    if not mona_path.exists():
        return t("common.error", error="Mona agent file missing")

    mona_agent = Agent.load(mona_path)
    service = HostAgentService(
        agent=mona_agent,
        armance_root=ctx.armance_root,
        config=ctx.cfg,
        sandbox_role="mona",
    )
    service.set_state(ctx.session.metadata)
    service.conversation = ctx.session.conversation

    # Pending run loads: if a previous turn fired /load-run, the artefacts
    # are queued in session metadata; surface them as a raw context block.
    pending = list(ctx.session.metadata.get("mona_pending_run_load", []))
    if pending:
        from armance.service.workflow_runs import load_run
        blocks: list[str] = []
        for entry in pending:
            wf, rid = entry.split("::", 1)
            files = load_run(ctx.armance_root, wf, rid)
            if not files:
                continue
            body = "\n\n".join(
                f"### `{name}`\n{content[:6000]}" for name, content in files.items()
            )
            blocks.append(f"## Workflow run `{wf}/{rid}`\n\n{body}")
        if blocks:
            service._pending_raw_inject = "\n\n---\n\n".join(blocks)
        ctx.session.metadata["mona_pending_run_load"] = []

    try:
        reply = await service.dialogue(text)
    except Exception as exc:
        logger.exception("Mona dialogue failed")
        return t("common.error", error=str(exc))

    ctx.session.metadata.update(service.get_state())
    reply = scrub_reply(reply, agent_role="mona")

    # Save deliverable tag
    save_match = _SAVE_TAG.search(reply)
    if save_match:
        basename = re.sub(r"[^\w-]", "_", save_match.group(1).strip())[:64] or "synthesis"
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out = ctx.armance_root / "docs" / f"mona-{basename}-{ts}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        # Strip the tag itself from the saved content so the doc reads clean.
        body = _SAVE_TAG.sub("", reply).strip()
        out.write_text(body, encoding="utf-8")
        reply = _SAVE_TAG.sub("", reply).strip()
        reply += "\n\n" + t(
            "mona.deliverable_saved",
            path=str(out.relative_to(ctx.armance_root)),
        )

    # Load-run tag — queue for the NEXT turn so the raw artefacts land in
    # Mona's context window.
    load_match = _LOAD_TAG.search(reply)
    if load_match:
        wf, rid = load_match.group(1).strip(), load_match.group(2).strip()
        pending = list(ctx.session.metadata.get("mona_pending_run_load", []))
        pending.append(f"{wf}::{rid}")
        ctx.session.metadata["mona_pending_run_load"] = pending
        reply = _LOAD_TAG.sub("", reply).strip()
        reply += "\n\n" + t("mona.run_queued", workflow=wf, run_id=rid)

    ctx.session.save()
    ctx._last_output = reply
    return reply
