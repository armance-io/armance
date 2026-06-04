"""Host agent (Armance) service — open-space greeter and router.

This module implements the host agent service that:
- start(): read manifest, list versions, render greet
- dialogue(user_text): stream LLM response, detect intents (/save, switch, etc.)
- freeze(slug?): compose new L0 from buffer + previous L0; write file; update manifest

Spec refs: 03_agents.md (Armance), 12_implementation_plan.md (T-09, T-15c)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable

from armance.core.models.agent import Agent
from armance.core.models import ContextVersion
from armance.core.models.context import (
    write_manifest,
    scan_sources,
)
from armance.core.models.conversation import Conversation
from armance.config import Config
from armance.service.llm_service import get_client, call_with_ledger

logger = logging.getLogger(__name__)


# Back-compat: handlers import these names. Real impl lives in agent_sandbox.


def _read_doc_text(path: "Path") -> str:
    """Extract plain text from a doc file regardless of format.

    .md/.txt → raw read. .pdf/.docx/.doc → reuse the ingestion loaders so
    /library load works on the same set of formats the indexer accepts.
    Failures degrade silently to empty string — the caller skips empty.
    """
    suffix = path.suffix.lower()
    try:
        if suffix in (".md", ".txt", ".text", ""):
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            from armance.storage.ingestion import load_pdf
            return "\n\n".join(c.text for c in load_pdf(path))
        if suffix in (".docx", ".doc"):
            from armance.storage.ingestion import load_docx
            return "\n\n".join(c.text for c in load_docx(path))
    except Exception:
        logger.exception("doc text extract failed: %s", path)
    return ""


class HostAgentService:
    """Service for the host agent (Armance)."""

    def __init__(
        self,
        agent: Agent,
        armance_root: Path,
        config: Config,
        on_token: Callable[[str], None] | None = None,
        sandbox_role: str = "armance",
        event_bus: "Any | None" = None,
    ) -> None:
        self.agent = agent
        self.armance_root = armance_root
        self.config = config
        self.on_token = on_token  # None → no-op in bridge_on_token
        self.event_bus = event_bus
        # Per-role tag allow-list applied in dialogue(). Pass "kim" / "malik"
        # / "mona" / "specialist" to scope the available [EXECUTE:/...] tags.
        self.sandbox_role = sandbox_role
        self.conversation = Conversation(agent=agent.name)
        self._buffer: list[str] = []
        self._has_seen_brief: bool = False
        self._cached_brief: str = ""
        self._cached_proposals: list = []  # list[JobProposal]
        self._pending_recruit_brief: str = ""
        # Injected by tui_bridge / handlers: frozen project brief + team roster
        self._project_brief: str = ""
        self._team_roster: list = []  # list[Agent]
        # Files queued for raw injection on next LLM call (set by [EXECUTE:/load:X])
        self._pending_load: list[str] = []
        # Mutable reference to the host session metadata (set by set_state).
        # Holds session-only "read" docs under key "library_read_session".
        self._session_meta_cache: dict = {}

    def set_state(self, metadata: dict) -> None:
        """Rehydrate state from metadata dict (Task C-05)."""
        self._buffer = list(metadata.get("host_buffer", []))
        self._has_seen_brief = bool(metadata.get("host_has_seen_brief", False))
        self._cached_brief = str(metadata.get("host_cached_brief", ""))
        self._pending_recruit_brief = str(metadata.get("host_pending_recruit_brief", ""))
        self._pending_load = list(metadata.get("host_pending_load", []))
        # Keep a *reference* to the session metadata so mutations to
        # library_read_session (and similar) propagate back without an explicit
        # write. The session save() reads this same dict.
        self._session_meta_cache = metadata

        # Rehydrate cached proposals
        from armance.service.agents.recruiter_agent import JobProposal
        self._cached_proposals = [
            JobProposal.model_validate(p) for p in metadata.get("host_cached_proposals", [])
        ]

    def get_state(self) -> dict:
        """Export state to metadata dict (Task C-05)."""
        return {
            "host_buffer": self._buffer,
            "host_has_seen_brief": self._has_seen_brief,
            "host_cached_brief": self._cached_brief,
            "host_pending_recruit_brief": self._pending_recruit_brief,
            "host_pending_load": self._pending_load,
            "host_cached_proposals": [
                p.model_dump() for p in self._cached_proposals
            ],
        }

    async def start(self) -> str:
        """Read manifest, list versions, render greet."""
        # Load latest context version
        context_dir = self.armance_root / "context"
        context_dir.mkdir(parents=True, exist_ok=True)
        l0_dir = context_dir / "L0"

        # Find latest L0 file: context/L0/v<NNN>_*.md
        latest_l0: Path | None = None
        l0_version = 0
        if l0_dir.exists():
            for p in l0_dir.glob("v*.md"):
                m = re.match(r"^v(\d+)_", p.name)
                if m:
                    v = int(m.group(1))
                    if v > l0_version:
                        l0_version = v
                        latest_l0 = p

        # Build greeting
        greeting = [
            f"Welcome to Armance! Session: {self.conversation.agent}",
            "",
        ]

        if latest_l0 and latest_l0.exists():
            greeting.append(f"Loaded context version: L0 v{l0_version:03d} ({latest_l0.name})")
            greeting.append("")
            greeting.append("Type your project description or question below.")
        else:
            greeting.append("No context loaded yet.")
            greeting.append("Describe your project to build shared context.")

        return "\n".join(greeting)

    async def dialogue(self, user_text: str) -> str:
        """Process one user turn.

        Armance's strategy is entirely LLM-driven:
          1. Slash commands are handled directly by Python.
          2. Everything else goes to the LLM, which semantically assesses
             whether the project context is rich enough and decides when
             to propose /save, suggest Malik, or keep asking questions.

        The system prompt is Armance's sole "brain" for context assessment
        and routing decisions. No Python heuristics gate his behaviour.
        """
        self.conversation.append("user", user_text)

        # Slash commands — handle directly
        intent = self._detect_intent(user_text)
        if intent == "save":
            return await self._handle_save()
        elif intent == "switch":
            return self._handle_switch(user_text)
        elif intent == "quit":
            return "[quit]"
        elif intent == "help":
            return self._handle_help()
        elif intent == "role":
            return await self._handle_role(user_text)

        # Accumulate every substantive turn in the buffer
        stripped = user_text.strip()
        if stripped and not self._is_greeting(stripped):
            self._buffer.append(stripped)
            try:
                from armance.service.context_service import ContextService
                ContextService(self.armance_root).cache_append(stripped)
            except Exception:
                logger.debug("cache append from buffer failed", exc_info=True)

        # Everything else: the LLM decides (ask questions, mirror back,
        # propose /save, suggest Malik — all via the system prompt).
        reply = await self._call_llm()

        # Normalise [EXECUTE:/save:<title>] → [EXECUTE:/save] (no parameter).
        import re as _re_save
        reply = _re_save.sub(r"\[EXECUTE:/save:[^\]]+\]", "[EXECUTE:/save]", reply)

        # Three-layer scrub: <tool_call> markup, repeated loops, per-role
        # tag allow-list. Default sandbox_role = 'armance'; Kim chat shell
        # injects 'kim' so /workflow-* survives.
        from armance.service.agent_sandbox import scrub_reply
        reply = scrub_reply(reply, agent_role=self.sandbox_role)

        # Semantic command interception
        if "[EXECUTE:/save]" in reply:
            reply = reply.replace("[EXECUTE:/save]", "").strip()
            # Gate: only execute if the current user turn looks like a
            # confirmation. Weak free models sometimes emit the tag in the same
            # turn where they *propose* saving (before the user answered).
            if self._is_confirmation(user_text):
                try:
                    save_msg = await self._handle_save()
                    reply += f"\n\n*(System: {save_msg})*"
                except Exception as e:
                    reply += f"\n\n*(System: failed to save context: {e})*"
            else:
                logger.warning(
                    "Armance emitted [EXECUTE:/save] but user turn is not a "
                    "confirmation (%r) — tag suppressed", user_text[:80]
                )

        import re as _re

        # New unified [EXECUTE:/library-*] tags (preferred). Legacy tags
        # (/ingest-docs, /rag-status, /load:X, /forget:X) are kept as aliases.
        # Accept [EXECUTE:/library-index] AND [EXECUTE:/library-index:<file>]
        # — the LLM sometimes emits the parameterised form even when the
        # index tag is global. We treat both as a full ingest.
        index_pattern = r"\[EXECUTE:/(?:library-index|ingest-docs)(?::[^\]]+)?\]"
        if _re.search(index_pattern, reply):
            reply = _re.sub(index_pattern, "", reply).strip()
            ingest_msg = await self._handle_ingest_docs()
            reply += f"\n\n{ingest_msg}"

        if "[EXECUTE:/library-status]" in reply or "[EXECUTE:/rag-status]" in reply:
            reply = reply.replace("[EXECUTE:/library-status]", "").strip()
            reply = reply.replace("[EXECUTE:/rag-status]", "").strip()
            rag_msg = self._handle_rag_status()
            reply += f"\n\n{rag_msg}"

        # [EXECUTE:/library-load:<filename>] (or legacy /load:X)
        load_match = _re.search(r"\[EXECUTE:/(?:library-load|load):([^\]]+)\]", reply)
        if load_match:
            fname = load_match.group(1).strip()
            reply = _re.sub(r"\[EXECUTE:/(?:library-load|load):[^\]]+\]", "", reply).strip()
            load_msg = await self._handle_load_doc(fname)
            reply += f"\n\n{load_msg}"

        # [EXECUTE:/library-unload:<filename>]
        unload_match = _re.search(r"\[EXECUTE:/library-unload:([^\]]+)\]", reply)
        if unload_match:
            fname = unload_match.group(1).strip()
            reply = _re.sub(r"\[EXECUTE:/library-unload:[^\]]+\]", "", reply).strip()
            unload_msg = self._handle_unload_doc(fname)
            reply += f"\n\n{unload_msg}"

        # [EXECUTE:/library-unindex:<filename>] (or legacy /forget:X)
        forget_match = _re.search(r"\[EXECUTE:/(?:library-unindex|forget):([^\]]+)\]", reply)
        if forget_match:
            fname = forget_match.group(1).strip()
            reply = _re.sub(r"\[EXECUTE:/(?:library-unindex|forget):[^\]]+\]", "", reply).strip()
            forget_msg = self._handle_forget_doc(fname)
            reply += f"\n\n{forget_msg}"

        return reply

    def _is_greeting(self, text: str) -> bool:
        """Return True if the text is a bare greeting with no project content."""
        stripped = text.strip().lower()
        greetings = {
            "hi", "hello", "hey", "hola", "bonjour", "hallo", "hi there",
            "hello there", "good morning", "good afternoon", "good evening",
            "howdy", "sup", "yo", "greetings",
        }
        if stripped in greetings:
            return True
        if len(stripped.split()) <= 3 and any(g in stripped for g in greetings):
            return True
        return False

    async def _call_llm(self) -> str:
        """Call the LLM with the full conversation history and system prompt."""
        system_prompt = self._build_system_prompt()

        last_user = next(
            (t.content for t in reversed(self.conversation.turns) if t.role == "user"),
            "",
        )

        # Load raw doc content when:
        #   (a) user message contains explicit read/look-at intent OR
        #   (b) user message names a file currently in .armance/docs/ OR
        #   (c) self._pending_load was set by a prior [EXECUTE:/load:<file>] tag
        forced = ""
        try:
            lowered = (last_user or "").lower()
            read_intent_words = (
                # FR: any verb suggesting reading/looking/summarising
                "lis ", "lis-", "lit ", "regarde", "consulte", "ouvre",
                "intègre", "integre", "intégrer", "intégrez",
                "ingère", "ingérer", "résume", "resume",
                "tu peux voir", "vois ", "checke", "check ",
                "dans les doc", "dans le doc", "dans .armance/docs",
                "j'ai mis", "j'ai déposé", "j'ai ajouté",
                # EN
                "read ", "look at", "check ", "open ", "summarize", "summarise",
                "ingest ", "in the doc", "in .armance/docs", "i dropped", "i added",
            )
            wants_doc_action = any(t in lowered for t in read_intent_words)

            # Detect filenames present in .armance/docs/ mentioned by user
            docs_dir = self.armance_root / "docs"
            named_files: list[str] = []
            if docs_dir.exists():
                for f in docs_dir.rglob("*"):
                    if not f.is_file() or f.name.startswith("."):
                        continue
                    if f.suffix.lower() not in (".pdf", ".md", ".txt", ".docx"):
                        continue
                    if f.name.lower() in lowered or f.stem.lower() in lowered:
                        named_files.append(f.name)

            pending = list(getattr(self, "_pending_load", []) or [])
            # "Read" set: docs the user wants every agent (Armance included)
            # to keep in mind for this session and/or persistently.
            from armance.storage.library_state import effective_read_set
            read_set = effective_read_set(self.armance_root, self._session_meta_cache)
            if wants_doc_action or named_files or pending or read_set:
                only = set(named_files) | set(pending) | read_set
                forced = self._load_docs_raw(
                    max_chars_per_file=6000,
                    only_files=only or None,
                )
                # Clear pending (one-shot). Read set is sticky.
                self._pending_load = []
        except Exception:
            logger.debug("doc force-load skipped", exc_info=True)
        if forced:
            system_prompt = f"{system_prompt}\n\n## Document contents (raw)\n{forced}"

        # Mona's [EXECUTE:/load-run:...] queues raw run artefacts here.
        raw_inject = getattr(self, "_pending_raw_inject", "") or ""
        if raw_inject:
            system_prompt = f"{system_prompt}\n\n{raw_inject}"
            self._pending_raw_inject = ""

        if not forced and not raw_inject:
            # Standard path: top-k RAG injection keyed on the last user turn.
            try:
                from armance.service.agents._rag_inject import inject_rag_section
                rag_section = await inject_rag_section(
                    self.armance_root, last_user, k=3, config=self.config
                )
                if rag_section:
                    system_prompt = f"{system_prompt}\n\n{rag_section}"
            except Exception:
                logger.debug("RAG injection skipped", exc_info=True)

        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        for turn in self.conversation.turns[-12:]:
            messages.append({"role": turn.role, "content": turn.content})

        client = get_client(self.agent.provider, self.config)

        from armance.service.agents._streaming_bridge import (
            AgentStreamingEmitter,
            bridge_on_token,
        )
        emitter = AgentStreamingEmitter(bus=self.event_bus, agent_name=self.agent.name)
        await emitter.start()
        effective_on_token = bridge_on_token(original=self.on_token, emitter=emitter)

        try:
            response = await call_with_ledger(
                client,
                self.agent.name,
                messages,
                self.agent.model,
                ledger=None,
                on_token=effective_on_token,
                provider=self.agent.provider,
            )
        finally:
            await emitter.end()

        full_response = response.text.strip()
        self.conversation.append("assistant", full_response)
        return full_response

    async def _handle_malik_handoff(self, brief: str) -> str:
        """Generate a contextual @Malik recruitment request via LLM."""
        system_prompt = (
            "You are Armance, the host of Armance. The user wants to recruit a "
            "specialist via Malik (the HR recruiter). Based on the project context "
            "and the user's request, generate a concise, natural message to Malik "
            "that specifies the role needed and key context. "
            "Format: '@Malik, recrute un <métier> pour <contexte>.' "
            "Do NOT include any markdown formatting or code fences."
        )
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        # Add recent conversation context (last 6 turns)
        for turn in self.conversation.turns[-6:]:
            messages.append({"role": turn.role, "content": turn.content})
        # Add the current request as the user message
        messages.append({"role": "user", "content": f"Je veux recruter : {brief}"})

        client = get_client(self.agent.provider, self.config)
        response = await call_with_ledger(
            client, self.agent.name, messages, self.agent.model, ledger=None,
            provider=self.agent.provider,
        )
        return response.text.strip()

    async def freeze(self, slug: str | None = None) -> ContextVersion:
        """Compose new L0 from buffer + previous L0; write file; update manifest.

        Path format: context/L0/v<NNN>_<date>_<slug>.md  (spec §12)
        """
        from armance.service.context_service import ContextService

        ctx_svc = ContextService(self.armance_root)

        # Get existing L0 body (without frontmatter)
        prev_body = (ctx_svc.read_l0_body() or "").strip()
        cache_content = ctx_svc.read_cache()
        buffer_content = (cache_content or "\n".join(self._buffer)).strip()

        # Build full dialogue transcript for LLM compilation.
        # Richer than buffer alone: captures context even when buffer has short confirmations.
        dialogue_transcript = ""
        if self.conversation and self.conversation.turns:
            lines: list[str] = []
            for turn in self.conversation.turns:
                role_label = "User" if turn.role == "user" else "Armance"
                content = (turn.content or "").strip()
                if content:
                    lines.append(f"**{role_label}**: {content}")
            dialogue_transcript = "\n\n".join(lines)

        # Fallback: harvest substantive user turns from the conversation if buffer is empty
        if not buffer_content and self.conversation and self.conversation.turns:
            user_lines: list[str] = []
            for turn in self.conversation.turns:
                if turn.role == "user":
                    t = (turn.content or "").strip()
                    if t and not self._is_greeting(t):
                        user_lines.append(t)
            buffer_content = "\n".join(user_lines).strip()

        if not prev_body and not buffer_content:
            body = "## L0\n\n### Goal\nProject context to be defined.\n"
        else:
            client = get_client(self.agent.provider, self.config)
            system_prompt = self.agent.effective_system_prompt(
                caveman_level="none",
                repo_root=self.armance_root,
            )

            transcript_section = (
                f"--- FULL CONVERSATION TRANSCRIPT ---\n{dialogue_transcript}\n"
                if dialogue_transcript
                else ""
            )
            compilation_prompt = f"""You are Armance, the host of Armance. Compile and synthesize the user's project context into a single, cohesive, professional L0 document.

Use ALL available sources below — previous context, buffer, and the full conversation — to extract every relevant fact about the project.

--- PREVIOUS CONTEXT (if any) ---
{prev_body}

--- UPDATED FACTS / BUFFER ---
{buffer_content}

{transcript_section}
---

Extract and organize project information into this Markdown layout:

## Goal
[A clear, concise statement of what the user wants to achieve]

## Key Requirements
[A bulleted list of requirements or features discussed]

## Context & Background
[Any historical, cultural, technical, or domain context mentioned]

## Next Steps
[Recommended next steps based on the conversation]

Preserve all factual content. Skip conversational filler. Output ONLY raw Markdown.
"""
            try:
                response = await call_with_ledger(
                    client,
                    self.agent.name,
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": compilation_prompt},
                    ],
                    self.agent.model,
                    ledger=None,
                    provider=self.agent.provider,
                )
                body = response.text.strip()
            except Exception:
                logger.exception("LLM compilation failed; falling back to raw buffer")
                body = ""

            # Fallback: LLM returned nothing useful → use raw buffer / prev body
            if len(body) < 80:
                if buffer_content and len(buffer_content) >= 80:
                    body = f"## L0\n\n### From conversation\n\n{buffer_content}"
                elif prev_body:
                    body = prev_body
                else:
                    body = f"## L0\n\n### From conversation\n\n{buffer_content}"

        effective_slug = slug or "context"

        # Write L0 via ContextService (handles frontmatter + manifest)
        path = ctx_svc.write_l0(
            body=body,
            slug=effective_slug,
            confirmed_by_user=True,
        )

        # Clear buffer
        self._buffer.clear()
        ctx_svc.clear_cache()

        # Derive version from filename
        m = re.match(r"^v(\d+)_", path.name)
        version = int(m.group(1)) if m else 1

        # Update manifest from sources
        sources = scan_sources(self.armance_root)
        write_manifest(self.armance_root, sources)

        return ContextVersion(
            level="L0",
            version=version,
            source_files=[str(s.path) for s in sources],
        )

    def _detect_recruit_decision(self, text: str):
        """Parse user reply to a role-proposal.

        Returns:
          "all"     — user accepts full team
          "none"    — user rejects (will adjust)
          list[str] — subset of role names to recruit
          None      — undetermined (fall through to LLM)
        """
        t = text.strip().lower()
        if not t:
            return None

        # Whole-team accept
        affirm_patterns = [
            "yes", "yep", "yeah", "ok", "okay", "sure", "go ahead",
            "do it", "proceed", "let's go", "lets go", "all of them",
            "all of these", "recruit all", "create all", "tous", "oui",
            "vas-y", "vas y", "toutes", "tout", "go", "all",
        ]
        for ap in affirm_patterns:
            if ap == t or t.startswith(ap + " ") or t.endswith(" " + ap) or f" {ap} " in f" {t} ":
                # But "no" inside ("no, all" → still all), prefer explicit affirm
                if not any(neg in t for neg in ("no ", "none", "aucun", "pas")):
                    return "all"

        # Whole-team reject
        reject_patterns = [
            "no", "nope", "none", "cancel", "stop", "skip",
            "non", "aucun", "annul",
        ]
        for rp in reject_patterns:
            if rp == t or t.startswith(rp + " ") or t.startswith(rp + ","):
                # exclude "no, only X" style which is a subset
                if not any(kw in t for kw in ("only", "just", "seulement", "juste")):
                    return "none"

        # Subset: look for proposal names in the text
        if self._cached_proposals:
            matched = [
                p.name for p in self._cached_proposals
                if p.name.lower() in t
            ]
            if matched:
                return matched

        return None

    def _detect_intent(self, text: str) -> str:
        """Detect intent from user text (e.g., /save, /switch).

        Checks for slash commands at the start of the input.
        """
        stripped = text.strip().lower()

        if stripped.startswith("/save"):
            return "save"
        if stripped.startswith("/switch"):
            return "switch"
        if stripped.startswith("/quit") or stripped == "/exit":
            return "quit"
        if stripped.startswith("/help"):
            return "help"
        if stripped.startswith("/role"):
            return "role"

        return "chat"

    def _handle_help(self) -> str:
        """Handle /help intent."""
        return """Armance commands:
/save       Freeze project context to L0
/switch <agent>  Switch to agent
/role list   List roles
/role show <name>  Show role details
/context list  List context versions
/context show [<version>]  Show context
/context load <version>  Activate version
/quit       Exit Armance
/help       Show this help
"""

    async def _handle_ingest_docs(self) -> str:
        """Execute sync_docs in a worker thread and return a human-readable
        confirmation. sync_docs is fully sync (httpx embed calls, sqlite-vec
        writes) — running it on the event loop freezes the TUI for the entire
        embed batch. asyncio.to_thread keeps the loop responsive (spinner +
        UI updates keep ticking)."""
        import asyncio

        from armance.nls import t
        try:
            from armance.storage.ingestion import sync_docs
            result = await asyncio.to_thread(
                sync_docs, self.armance_root, config=self.config
            )
            indexed = result.get("indexed", 0)
            skipped = result.get("skipped", 0)
            deleted = result.get("deleted", 0)
            error = result.get("error")

            # Explicit failure sentinel from sync_docs
            if error == "embed_init_failed":
                return t("system.error", body=t("ingest.embed_init_failed"))

            # Distinguish "no docs on disk" from "docs present, already up to date"
            if indexed == 0 and skipped == 0 and deleted == 0:
                docs_dir = self.armance_root / "docs"
                has_files = docs_dir.exists() and any(
                    p.is_file() and p.suffix.lower() in (".pdf", ".md", ".txt", ".docx")
                    for p in docs_dir.rglob("*")
                )
                if has_files:
                    return t("system.info", body=t("ingest.nothing_to_do"))
                return t("system.info", body=t("ingest.no_docs"))

            parts: list[str] = []
            chunks = result.get("chunks", 0)
            if indexed:
                parts.append(t("ingest.part_indexed", n=indexed))
                if chunks:
                    parts.append(t("ingest.part_chunks", n=chunks))
            if skipped:
                parts.append(t("ingest.part_skipped", n=skipped))
            if deleted:
                parts.append(t("ingest.part_deleted", n=deleted))
            body = " ; ".join(parts) + ". " + t("ingest.success_suffix")
            per = result.get("per_doc_chunks") or {}
            if per:
                body += "\n" + "\n".join(
                    t("ingest.per_doc_line", name=n, chunks=c)
                    for n, c in sorted(per.items())
                )
            return t("system.ok", body=body)
        except Exception as exc:
            logger.exception("ingest-docs failed")
            return t("system.error", body=t("ingest.failed", error=str(exc)))

    def _handle_rag_status(self) -> str:
        """Return formatted RAG status markdown."""
        from armance.nls import t
        try:
            from armance.storage.rag_status import get_rag_status, format_rag_status_markdown
            status = get_rag_status(self.armance_root, self.config)
            return format_rag_status_markdown(status)
        except Exception as exc:
            logger.exception("rag-status failed")
            return t("system.error", body=t("rag_status.failed", error=str(exc)))

    async def _handle_save(self) -> str:
        """Handle /save intent — freeze context to L0 via LLM-compiled freeze()."""
        from armance.service.context_service import ContextService
        ctx_svc = ContextService(self.armance_root)
        full_text = ctx_svc.read_cache() or "\n".join(self._buffer)
        cleaned = full_text.lower()
        for greeting in ["hello", "hi", "hey", "yo", "bonjour", "salut", "coucou", "merci", "thanks", "s'il te plaît", "please", "s'il vous plaît", "svp"]:
            cleaned = re.sub(r'\b' + re.escape(greeting) + r'\b', '', cleaned)
        alphanum = "".join(c for c in cleaned if c.isalnum())

        has_prior = bool((ctx_svc.read_l0_body() or "").strip())
        if len(alphanum) < 30 and not has_prior:
            return "error: context is too brief to save (minimum 30 non-greeting characters required to frame a project context)"

        try:
            version = await self.freeze()
        except Exception as exc:
            logger.exception("freeze failed")
            return f"error: freeze failed — {exc}"
        return f"context saved as L0_v{version.version:03d}"

    def _handle_switch(self, text: str) -> str:
        """Handle /switch intent."""
        # Extract agent name from text
        match = re.search(r"/switch\s+(\w+)", text, re.IGNORECASE)
        if match:
            return f"Switching to agent: {match.group(1)}"
        return "Usage: /switch <agent_name>"

    async def _handle_role(self, text: str) -> str:
        """Handle /role intent."""
        # Extract role action and arguments from text
        match = re.search(r"/role\s+(\w+)(?:\s+([^\s].*))?", text, re.IGNORECASE)
        if not match:
            return "Usage: /role <action> [args]"

        action = match.group(1).lower()
        args = match.group(2).strip() if match.group(2) else ""

        if action == "list":
            return await self._handle_role_list()
        elif action == "show":
            return await self._handle_role_show(args)
        elif action in ("add", "edit", "create"):
            return await self._handle_malik_handoff(args)
        else:
            return f"Unknown action: {action}"

    async def _handle_role_list(self) -> str:
        """Handle /role list action."""
        roles_dir = self.armance_root / "roles"
        if not roles_dir.exists():
            return "No roles found."

        roles = [f.stem for f in roles_dir.iterdir() if f.is_file() and f.suffix == ".md"]
        if not roles:
            return "No roles found."

        return "Roles:\n" + "\n".join(f"- {role}" for role in roles)

    async def _handle_role_show(self, name: str) -> str:
        """Handle /role show action."""
        if not name:
            return "Usage: /role show <name>"

        role_file = self.armance_root / "roles" / f"{name}.md"
        if not role_file.exists():
            return f"Role '{name}' not found."

        content = role_file.read_text(encoding="utf-8")
        return f"Role '{name}':\n{content}"

    def _agents_exist(self) -> bool:
        """Check if any agents exist in the agents directory."""
        agents_dir = self.armance_root / "agents"
        if not agents_dir.exists():
            return False
        # Check for .md files that are not system agents
        for path in agents_dir.glob("*.md"):
            if path.stem not in ("system-context", "system-hr"):
                return True
        return False

    def _asks_what_to_do(self, text: str) -> bool:
        """Detect if user is asking what to do next / what can I do."""
        stripped = text.strip().lower()
        indicators = [
            "what can i", "what could i", "what should i", "what do i",
            "what's next", "what next", "next step", "next steps",
            "how do i start", "how to start", "get started", "how can i",
            "what can you", "what could you", "what do you suggest",
            "what do you recommend", "any suggestions", "any recommendations",
            "what's the next", "what is the next",
        ]
        for indicator in indicators:
            if indicator in stripped:
                return True
        return False

    async def _suggest_workflows(self) -> str:
        """Suggest workflows now that agents exist."""
        # List available workflows
        workflows_dir = self.armance_root / ".armance" / "workflows"
        workflows = []
        if workflows_dir.exists():
            for wf in workflows_dir.glob("*.yaml"):
                workflows.append(wf.stem)
            for wf in workflows_dir.glob("*.yml"):
                workflows.append(wf.stem)

        # List available roles
        roles_dir = self.armance_root / "roles"
        roles = []
        if roles_dir.exists():
            roles = [f.stem for f in roles_dir.iterdir() if f.is_file() and f.suffix == ".md"]

        lines = ["Now that you have agents set up, here are your options:"]
        lines.append("")

        if workflows:
            lines.append("**Available workflows:**")
            for wf in workflows:
                lines.append(f"  - `/workflow run {wf}` — Execute the '{wf}' workflow")
            lines.append("")

        if roles:
            lines.append("**Your roles:**")
            for r in roles:
                lines.append(f"  - `{r}` — Use `/switch {r}` to work with this role's agents")
            lines.append("")

        lines.append("**Other options:**")
        lines.append("  - `/workflow run brainstorm` — Three agents deliberate on your prompt")
        lines.append("  - `/task <domain> <prompt>` — Run a single agent")
        lines.append("  - Ask `@Malik` to recruit more agents for a role")
        lines.append("  - `armance index` (in shell) — Index documents for RAG context")

        return "\n".join(lines)

    def _is_confirmation(self, text: str) -> bool:
        """User says yes / go / vas-y / OK / d'accord / "oui, fige", etc."""
        t = text.strip().lower().rstrip(" .!?,;:")
        if not t:
            return False
        affirmations = {
            "oui", "ok", "okay", "d'accord", "daccord", "vas-y", "vas y",
            "go", "go alors", "go ahead", "yes", "yep", "yeah", "sure",
            "carrément", "carrement", "allons-y", "allons y", "feu",
            "parfait", "très bien", "tres bien", "ça marche", "ca marche",
            "fais-le", "fais le", "do it", "let's do it", "lets do it",
        }
        if t in affirmations:
            return True
        # Affirmative opener: the first word is an affirmation, regardless of
        # trailing punctuation ("oui, tu peux figer" → first token "oui").
        # Splitting on non-word chars means the comma after "oui" no longer
        # defeats the match (the old `startswith("oui ")` did).
        first = re.split(r"[\s,.;:!?]+", t, maxsplit=1)[0]
        openers = {"oui", "ok", "okay", "yes", "yep", "yeah", "go", "ouais",
                   "carrément", "carrement", "parfait", "exactement", "exact"}
        if first in openers:
            return True
        # Imperative confirmations: user tells Armance to go ahead / freeze.
        # Match verb stems (figer/fige/figez, valider/valide…) at a word start.
        for stem in ("fais", "fig", "fixe", "valid", "confirm", "enregistr"):
            if re.search(r"\b" + stem, t):
                return True
        return False

    def _announces_malik_handoff(self, text: str) -> bool:
        """Armance's reply announces he will pass the brief to Malik."""
        t = text.lower()
        markers = [
            "demand", "transmet", "passer la main",
            "passe la main", "passerai", "transmettrai",
            "ask malik", "tell malik", "hand off",
        ]
        # Need both an action verb AND mention of Malik
        has_malik = "malik" in t
        has_action = any(m in t for m in markers)
        return has_malik and has_action

    def _last_user_brief(self) -> str:
        """Find the most recent substantive user turn (skip confirmations)."""
        for turn in reversed(self.conversation.turns):
            if turn.role != "user":
                continue
            content = turn.content.strip()
            if len(content.split()) >= 5 and not self._is_confirmation(content):
                return content
        return ""

    def _wants_recruitment(self, text: str) -> bool:
        """Deprecated — kept for back-compat only."""
        return False

    def _load_docs_raw(
        self,
        *,
        max_chars_per_file: int = 8000,
        only_files: set[str] | None = None,
    ) -> str:
        """Concatenate the raw text of readable files in `.armance/docs/`.

        If `only_files` is given, restrict to those filenames (basename match).
        """
        docs_dir = self.armance_root / "docs"
        if not docs_dir.exists():
            return ""
        out: list[str] = []
        for f in sorted(docs_dir.rglob("*")):
            if not f.is_file() or f.name.startswith("."):
                continue
            suffix = f.suffix.lower()
            if suffix not in (".md", ".txt", ".pdf", ".docx", ".doc"):
                continue
            if only_files is not None and f.name not in only_files:
                continue
            content = _read_doc_text(f)
            if not content or not content.strip():
                continue
            rel = f.relative_to(docs_dir).as_posix()
            out.append(f"### `{rel}`\n{content[:max_chars_per_file]}")
        return "\n\n".join(out)

    async def _handle_load_doc(self, filename: str) -> str:
        """Mark a doc 'read' session-wide AND queue raw injection for next turn."""
        from armance.nls import t
        from armance.storage.library_state import mark_read
        docs_dir = self.armance_root / "docs"
        target = None
        for f in docs_dir.rglob("*"):
            if f.is_file() and f.name == filename:
                target = f
                break
        if target is None:
            return t("system.error", body=t("load.not_found", filename=filename))
        if target.suffix.lower() not in (".md", ".txt", ".pdf", ".docx", ".doc"):
            return t(
                "system.warn",
                body=t("load.binary_format", filename=filename, suffix=target.suffix),
            )
        # Persist session-only 'read' state (will be visible to other agents too).
        mark_read(self.armance_root, filename, persist=False, session_meta=self._session_meta_cache)
        pending = list(getattr(self, "_pending_load", []) or [])
        if filename not in pending:
            pending.append(filename)
        self._pending_load = pending
        return t("load.queued", filename=filename)

    def _handle_unload_doc(self, filename: str) -> str:
        """Remove a doc from the 'read' set (session + persistent)."""
        from armance.nls import t
        from armance.storage.library_state import unmark_read
        removed = unmark_read(self.armance_root, filename, self._session_meta_cache)
        if removed:
            return t("library.unload_ok", filename=filename)
        return t("system.info", body=t("library.unload_not_loaded", filename=filename))

    def _handle_forget_doc(self, filename: str) -> str:
        """Remove a doc from the RAG library (manifest + sqlite chunks)."""
        from armance.nls import t
        try:
            from armance.storage.rag_status import forget_doc
            return forget_doc(self.armance_root, filename)
        except Exception as exc:
            logger.exception("forget-doc failed")
            return t("system.error", body=t("forget.failed", error=str(exc)))

    def _load_armance_concepts(self) -> str:
        """Load the caveman-tight concepts KB so Armance can self-explain
        Armance when the user is lost. Cached on first call."""
        if hasattr(self, "_concepts_cache"):
            return self._concepts_cache
        from pathlib import Path as _Path
        concepts_path = _Path(__file__).parent / "builtin" / "_armance_concepts.md"
        try:
            self._concepts_cache = concepts_path.read_text(encoding="utf-8")
        except Exception:
            self._concepts_cache = ""
        return self._concepts_cache

    def _build_library_section(self) -> str:
        """One-liner banner about library availability — drives Armance's
        menu choices (skips 'A indexer' / 'C both' when library is inactive)."""
        from armance.nls import t
        from armance.storage.library_availability import library_summary
        summary = library_summary(self.armance_root, self.config)
        if summary["active"]:
            return t(
                "library_status.active",
                provider=summary["provider"],
                model=summary["model"],
                docs=summary["docs"],
                chunks=summary["chunks"],
            )
        return t("library_status.inactive")

    def _build_docs_section(self) -> str:
        """Inject docs/ listing + diff vs last snapshot + library (RAG) state."""
        docs_dir = self.armance_root / "docs"
        if not docs_dir.exists():
            return ""
        files = sorted(
            p for p in docs_dir.rglob("*")
            if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in (".pdf", ".md", ".txt", ".docx")
        )
        # Load ingestion manifest (= RAG library state)
        manifest_path = docs_dir.parent / "vector" / "manifest.json"
        indexed: set[str] = set()
        if manifest_path.exists():
            try:
                import json as _json
                indexed = set((_json.loads(manifest_path.read_text()) or {}).keys())
            except Exception:
                indexed = set()

        # Load previous-session snapshot for diff detection
        snapshot_path = docs_dir.parent / "vector" / "docs_snapshot.json"
        prev_files: set[str] = set()
        if snapshot_path.exists():
            try:
                import json as _json
                prev_files = set(_json.loads(snapshot_path.read_text()) or [])
            except Exception:
                prev_files = set()

        current_files = {f.relative_to(docs_dir).as_posix() for f in files}
        # Save current snapshot for next session
        try:
            import json as _json
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(_json.dumps(sorted(current_files)))
        except Exception:
            logger.debug("docs snapshot save failed", exc_info=True)

        added = current_files - prev_files
        removed = prev_files - current_files
        orphans = indexed - current_files  # in library but file removed from disk

        from armance.nls import t
        from armance.storage.library_availability import is_library_available
        if not files and not orphans:
            body_key = (
                "docs_section.empty_body"
                if is_library_available(self.config)
                else "docs_section.empty_body_no_library"
            )
            return t("docs_section.empty_title") + "\n" + t(body_key)

        lines = [t("docs_section.title")]
        for f in files:
            rel = f.relative_to(docs_dir).as_posix()
            in_lib = rel in indexed
            status_tag = t("docs_section.status_retained") if in_lib else t("docs_section.status_unread")
            lines.append(t("docs_section.file_line", name=rel, status=status_tag))

        if orphans:
            lines.append("")
            lines.append(t("docs_section.orphans_header"))
            for name in sorted(orphans):
                lines.append(t("docs_section.orphan_line", name=name))

        if added or removed:
            lines.append("")
            lines.append(t("docs_section.changes_header"))
            for name in sorted(added):
                lines.append(t("docs_section.change_added", name=name))
            for name in sorted(removed):
                lines.append(t("docs_section.change_removed", name=name))

        lines.append(t("docs_section.rules"))
        return "\n".join(lines)

    def _build_system_prompt(self) -> str:
        """Build system prompt, injecting project brief and team roster if known."""
        base_prompt = self.agent.effective_system_prompt(
            caveman_level="none",
            repo_root=self.armance_root,
        )

        sections = [base_prompt]

        # Inject library availability banner FIRST (Armance uses it to gate
        # the A/B/C/D doc menu — without a library, A and C disappear).
        try:
            sections.append(self._build_library_section())
        except Exception:
            logger.debug("library status section failed", exc_info=True)

        # Inject documents listing (what is in .armance/docs/, ingestion state)
        try:
            docs_section = self._build_docs_section()
            if docs_section:
                sections.append(docs_section)
        except Exception:
            logger.debug("docs listing failed", exc_info=True)

        # Armance concepts knowledge base (caveman-tight, ~50 lines).
        # Armance can use it to answer 'comment ça marche / pourquoi pas de
        # bibliothèque / comment configurer X' without leaving the chat.
        try:
            sections.append(self._load_armance_concepts())
        except Exception:
            logger.debug("armance concepts inject failed", exc_info=True)

        # Inject frozen project brief (so Armance never re-asks)
        if self._project_brief:
            sections.append(
                "## Current project (already shared by the CEO)\n"
                f"{self._project_brief.strip()}\n"
                "Do NOT re-ask the user to describe this. Reference it as needed."
            )

        # Pending shared cache (incremental notes not yet frozen into L0).
        try:
            from armance.service.context_service import ContextService
            _cache = ContextService(self.armance_root).read_cache()
            if _cache:
                sections.append(
                    "## Pending context cache (not yet saved)\n"
                    f"{_cache}\n"
                    "When this looks like a coherent milestone (or it grows large), "
                    "propose saving it: recap what you'd add, then emit "
                    "[EXECUTE:/save] ONLY after the user confirms."
                )
        except Exception:
            logger.debug("cache inject failed", exc_info=True)

        # Inject team roster
        if self._team_roster:
            roster_lines = ["## Team currently on board"]
            by_role: dict[str, list[str]] = {}
            for a in self._team_roster:
                role = (getattr(a, "role", None) or getattr(a, "domain", None) or "general")
                by_role.setdefault(role, []).append(
                    f"{a.name} ({getattr(a, 'persona', 'balanced')})"
                )
            for role in sorted(by_role):
                roster_lines.append(f"- **{role}**: " + ", ".join(by_role[role]))
            sections.append("\n".join(roster_lines))
        else:
            sections.append(
                "## Team currently on board\n"
                "**ROSTER IS EMPTY.** No user-recruited specialists exist yet. "
                "You MUST NOT invent agent names (no Aria, Bram, Serge, Mona, etc. "
                "as team members — those are staff meta-agents, not your roster). "
                "If asked to design or run a workflow, refuse and tell the user "
                "`@Malik, peux-tu recruter une équipe ?` then STOP."
            )

        # Voice overlay LAST — weak models follow the final instruction best.
        try:
            from armance.service.agents._voice_overlay import voice_overlay
            sections.append(voice_overlay(getattr(self.config, "language", "en")))
        except Exception:
            pass

        return "\n\n".join(sections)
