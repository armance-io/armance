"""Main screen for Armance TUI.

Layout:
  Header
  body: ChatView | Sidebar
  HITLBanner (collapsed when not active)
  InputBar
  Footer
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header

from armance.config import Config
from armance.service.llm_service import TokenLedger
from armance.service.session import Session

from armance.client.tui.widgets.chat import ChatView
from armance.client.tui.widgets.footer import HITLBanner
from armance.client.tui.widgets.input import InputBar
from armance.client.tui.widgets.sidebar import Sidebar
from armance.client.tui.widgets.thinking import ThinkingIndicator

logger = logging.getLogger(__name__)


class MainScreen(Screen[int]):
    """Main screen: Header / [Chat | Sidebar] / HITL / Input / Footer."""

    # Allow text selection in the chat (Textual ≥ 0.79)
    ALLOW_SELECT = True

    DEFAULT_CSS = """
    MainScreen {
        layout: vertical;
        background: $background;
    }

    #body {
        layout: horizontal;
        height: 1fr;
        background: $background;
    }

    #content-area {
        width: 1fr;
        height: 1fr;
        background: $background;
    }

    Sidebar {
        width: 30;
        height: 1fr;
        background: $panel;
        border-left: vkey $primary;
    }

    HITLBanner {
        height: 0;
    }

    HITLBanner.visible {
        height: 1;
    }

    #thinking {
        height: 1;
        width: 100%;
        background: $panel;
        padding: 0 2;
        opacity: 0;
        dock: bottom;
    }

    #thinking.visible {
        opacity: 1;
    }

    InputBar {
        height: 3;
        background: $panel;
        border-top: hkey $primary;
    }
    """

    BINDINGS = [
        Binding("tab", "cycle_focus", "Cycle focus", show=False),
        Binding("ctrl+k", "clear_chat", "Clear", show=True),
        Binding("ctrl+s", "save_state", "Save session", show=True, priority=True),
        Binding("ctrl+c", "clear_input", "Clear input", show=False, priority=True),
        Binding("ctrl+q", "request_quit", "Quit", show=True, priority=True),
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("question_mark", "show_keybindings", "Keys?", show=False),
        Binding("alt+shift+left", "sidebar_grow", "Sidebar ◀", show=False, priority=True),
        Binding("alt+shift+right", "sidebar_shrink", "Sidebar ▶", show=False, priority=True),
    ]

    _sidebar_width: int = 30

    def __init__(
        self,
        armance_root: Path,
        cfg: Config,
        session: Session,
        ledger: TokenLedger,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.armance_root = armance_root
        self.cfg = cfg
        self.session = session
        self.state = session.state
        self.ledger = ledger
        self._loop_ctx: Any = None  # built lazily on first input
        self._quit_in_progress: bool = False  # guard against Ctrl+Q stacking
        self._active_workers: dict[str, int] = {}  # agent_name → count of running workers

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="body"):
            with Container(id="content-area"):
                yield ChatView()
                yield ThinkingIndicator(id="thinking")
            yield Sidebar(id="sidebar")
        yield HITLBanner()
        yield InputBar()
        yield Footer()

    def on_mount(self) -> None:
        logger.info("MainScreen mounting session=%s", self.state.id)
        self.title = "Armance"
        self.sub_title = f"session {self.state.id[:8]}"

        # Build LoopContext eagerly so sidebar can show the loaded agents
        from armance.service.tui_bridge import make_loop_context
        from armance.client.tui.checkpoint_prompt import TerminalCheckpointHandler
        try:
            self._loop_ctx = make_loop_context(
                self.armance_root,
                self.cfg,
                self.state,
                self.session,
                self.ledger,
                checkpoint_handler=TerminalCheckpointHandler(),
            )
        except Exception:
            logger.exception("failed to build LoopContext")
            self._loop_ctx = None

        self._refresh_sidebar()
        self._refresh_meta_models()
        self.set_interval(1.0, self._refresh_sidebar)
        self.set_interval(5.0, self._refresh_meta_models)
        self.set_interval(2.0, self._refresh_token_display)

        # Greeting
        from armance.nls import t as _t
        chat = self.query_one(ChatView)
        chat.append_message(
            "system",
            _t("greeting.welcome"),
            label="armance",
        )

        # Load history
        from armance.service.tui_bridge import agent_label
        for turn in self.session.conversation.turns:
            label, role = agent_label(turn.agent, self._loop_ctx.agents if self._loop_ctx else [])
            chat.append_message(role, turn.content, label=label)
        chat.append_message(
            "system",
            _t("greeting.hint"),
            label="armance",
        )

        # Default to system-context agent
        if self.state.current_agent is None:
            self.state.current_agent = "system-context"

        try:
            self.query_one(InputBar).focus()
        except Exception:
            logger.exception("failed to focus input bar")

    # ------------------------------------------------------------------
    # Sidebar refresh
    # ------------------------------------------------------------------

    def _refresh_token_display(self) -> None:
        """Update sub_title with live token + cost; add per-agent breakdown when active."""
        try:
            snap = self.ledger.snapshot()
            total = snap.get("total", {})
            ti = total.get("tokens_in", 0)
            to = total.get("tokens_out", 0)
            cost = total.get("cost_usd", 0.0)
            parts = [f"↑{ti:,} ↓{to:,} ${cost:.4f}"]

            # Current agent model + IN/OUT pricing (per MTok)
            active = self.state.current_agent
            if active:
                try:
                    from armance.core.models.agent import Agent
                    from armance.service.cost import lookup_price
                    agent_path = self.armance_root / "agents" / f"{active}.md"
                    if agent_path.exists():
                        ag = Agent.load(agent_path)
                        if ag.model:
                            price = lookup_price(
                                ag.model,
                                prices_override=getattr(self.cfg, "prices", None) or {},
                            )
                            short_model = ag.model.split("/", 1)[-1].replace(":free", "")
                            if price is None:
                                price_tag = "?"
                            elif price["input_per_mtok"] == 0 and price["output_per_mtok"] == 0:
                                price_tag = "free"
                            else:
                                price_tag = f"${price['input_per_mtok']:g}/${price['output_per_mtok']:g}/Mtok"
                            parts.append(f"{short_model}·{price_tag}")
                except Exception:
                    pass

            self.sub_title = " · ".join(parts)
        except Exception:
            pass

    def _refresh_meta_models(self) -> None:
        """Read model field from system-*.md files and push to sidebar cost pastilles."""
        try:
            from armance.core.models.agent import Agent
            agents_dir = self.armance_root / "agents"
            meta_map: dict[str, str] = {}
            for canonical in ("system-context", "system-hr", "system-orchestrator", "system-judge", "system-challenger"):
                p = agents_dir / f"{canonical}.md"
                if p.exists():
                    try:
                        a = Agent.load(p)
                        if a.model:
                            meta_map[canonical] = a.model
                    except Exception:
                        pass
            sidebar = self.query_one(Sidebar)
            sidebar.set_meta_models(meta_map)
        except Exception:
            pass

    def _refresh_sidebar(self, working_agent: str | None = None) -> None:
        """Update sidebar from current session/agent states and check for HITL."""
        if self._loop_ctx is None:
            return
            
        try:
            sidebar = self.query_one(Sidebar)
        except Exception:
            return

        # 1) Agents & Meta
        roles_data: dict[str, list[dict[str, Any]]] = {}
        hitl_agent = None
        
        for a in self._loop_ctx.agents:
            status = next((s for s in self._loop_ctx.statuses if s.name == a.name), None)
            state = status.state if status else "idle"
            
            # If this agent has an active worker, keep it marked working regardless
            # of which agent is currently selected.
            if (working_agent and a.name == working_agent) or self._active_workers.get(a.name, 0) > 0:
                state = "working"
                
            if state == "input-required":
                hitl_agent = a.name
                
            roles_data.setdefault(a.domain or "general", []).append(
                {
                    "name": a.name,
                    "state": state,
                    "active": (self.state.current_agent == a.name),
                    "persona": getattr(a, "persona", ""),
                    "model": getattr(a, "model", None),
                }
            )
        sidebar.set_agents(roles_data)
        sidebar.set_active_agent(self.state.current_agent)

        # 1.5) Library status badge — always visible (active or inactive).
        try:
            from armance.storage.library_availability import library_summary
            sidebar.set_library(library_summary(self.armance_root, self.cfg))
        except Exception:
            logger.debug("library badge refresh failed", exc_info=True)

        # 1.6) Workflows — scan .armance/workflows/*.yaml.
        try:
            wf_dir = self.armance_root / "workflows"
            wf_items: list[dict[str, Any]] = []
            if wf_dir.exists():
                for p in sorted(wf_dir.glob("*.yaml")):
                    wf_items.append({"name": p.stem, "working": False})
            sidebar.set_workflows(wf_items)
        except Exception:
            logger.debug("workflow sidebar refresh failed", exc_info=True)

        # 2) HITL Banner
        try:
            banner = self.query_one(HITLBanner)
            if hitl_agent:
                banner.show_for(hitl_agent)
            else:
                banner.hide()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_cycle_focus(self) -> None:
        focus_order = [InputBar, ChatView, Sidebar]
        try:
            idx = -1
            node: Any = self.focused
            while node is not None and idx == -1:
                for i, cls in enumerate(focus_order):
                    if isinstance(node, cls):
                        idx = i
                        break
                node = getattr(node, "parent", None)
            if idx == -1:
                idx = 0
            next_cls = focus_order[(idx + 1) % len(focus_order)]
            self.query_one(next_cls).focus()
        except Exception:
            logger.exception("cycle_focus failed")

    def action_clear_chat(self) -> None:
        self.query_one(ChatView).clear()

    def action_save_state(self) -> None:
        try:
            self.session.save()
            self.notify(
                "Session state saved (state.json + conversation). "
                "Use /save to freeze project context as L0.",
                severity="information",
                timeout=4,
            )
        except Exception as exc:
            self.notify(f"Save failed: {exc}", severity="error", timeout=4)

    def action_quit(self) -> None:
        self.app.exit(0)

    def _apply_sidebar_width(self) -> None:
        try:
            sidebar = self.query_one(Sidebar)
            sidebar.styles.width = self._sidebar_width
        except Exception:
            pass

    def action_sidebar_shrink(self) -> None:
        self._sidebar_width = max(10, self._sidebar_width - 5)
        self._apply_sidebar_width()

    def action_sidebar_grow(self) -> None:
        self._sidebar_width = min(100, self._sidebar_width + 5)
        self._apply_sidebar_width()

    def action_clear_input(self) -> None:
        """Ctrl+C: clear the input area. No quit (use Ctrl+Q to quit)."""
        from armance.client.tui.widgets.input import ChatInput
        try:
            self.query_one(ChatInput).clear()
        except Exception:
            pass

    def action_request_quit(self) -> None:
        """Ctrl+Q: save-or-discard prompt then exit. Guarded against re-entry
        so repeated presses do not stack popups."""
        if self._quit_in_progress:
            return
        self._quit_in_progress = True
        self.run_worker(self._quit_with_save_prompt(), exclusive=True)

    async def _quit_with_save_prompt(self) -> None:
        """Ask Y/N before exit. Save = persist host buffer to L0 + ledger flush."""
        from armance.nls import t as _t
        buffer = list(self.session.metadata.get("host_buffer", []))
        if not buffer:
            self.app.exit(0)
            return
        try:
            from armance.service.checkpoint import Checkpoint
            handler = self._loop_ctx.checkpoint_handler if self._loop_ctx else None
            if handler is None:
                self.app.exit(0)
                return
            resp = await handler.prompt(
                Checkpoint(id="quit.save", prompt=_t("quit.save_prompt"), kind="confirm")
            )
            if not resp.is_abort and resp.content == "yes":
                # Save WITHOUT calling the LLM — write the buffer as a freeze
                # note to context/L0/.
                try:
                    from armance.service.context_service import ContextService
                    ContextService(self.armance_root).append_quick_freeze("\n".join(buffer))
                    self.session.metadata["host_buffer"] = []
                    self.session.save()
                    self.notify(_t("quit.saved"), severity="information", timeout=2)
                except Exception:
                    logger.exception("quit save failed")
        except Exception:
            logger.exception("quit prompt failed")
        self.app.exit(0)

    def action_cancel(self) -> None:
        self.notify("Cancelled", severity="warning", timeout=2)

    def action_show_keybindings(self) -> None:
        self.notify(
            "Tab cycle · Ctrl+S save · Ctrl+Q quit · Ctrl+C clear input · Ctrl+K clear chat · "
            "Alt+◀/▶ resize sidebar · "
            "click [copy] on a message · /help for commands",
            timeout=4,
        )

    def _likely_triggers_malik(self, text: str) -> bool:
        """Cheap heuristic: user input that probably fires the recruit pipeline."""
        t = text.strip().lower().rstrip(" .!?,;:")
        if not t:
            return False
        affirmations = {
            "oui", "ok", "okay", "d'accord", "vas-y", "vas y", "go", "go alors",
            "yes", "yep", "yeah", "sure", "carrément", "fais-le", "fais le",
        }
        if t in affirmations:
            return getattr(self.state, "pending_recruit_brief", "") != ""
        keywords = ("recrut", "malik", "hire", "monte une équipe", "build a team")
        return any(k in t for k in keywords)

    def _handle_copy_command(self, raw: str) -> None:
        """Handle `/copy [N|all]` — copies a chat message as markdown."""
        chat = self.query_one(ChatView)
        parts = raw.split()
        target: str | None = parts[1] if len(parts) > 1 else None

        md: str | None
        if target is None:
            md = chat.get_last_markdown()
            label = "last message"
        elif target.lower() == "all":
            md = chat.get_full_transcript_markdown() or None
            label = "full transcript"
        else:
            try:
                idx = int(target)
                md = chat.get_message_markdown(idx)
                label = f"message #{idx}"
            except ValueError:
                self.notify("usage: /copy [N|all]", severity="warning", timeout=3)
                return

        if not md:
            self.notify("nothing to copy", severity="warning", timeout=2)
            return
        try:
            self.app.copy_to_clipboard(md)
            self.notify(f"copied {label} ({len(md)} chars markdown)", timeout=2)
        except Exception as exc:
            self.notify(f"copy failed: {exc}", severity="error", timeout=3)

    def action_copy_selection(self) -> None:
        """Copy currently-selected text (mouse drag) to clipboard."""
        try:
            selected = self.get_selected_text()
        except Exception:
            selected = None
        if not selected:
            self.notify("Nothing selected. Drag with mouse in chat to select.", timeout=3)
            return
        try:
            self.app.copy_to_clipboard(selected)
            self.notify(f"Copied {len(selected)} chars", severity="information", timeout=2)
        except Exception as exc:
            self.notify(f"Copy failed: {exc}", severity="error", timeout=3)

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
        """Echo user input, then dispatch async."""
        text = event.value
        chat = self.query_one(ChatView)
        chat.append_message("user", text)

        # Run dispatch as a worker so the UI stays responsive
        self.run_worker(self._handle_input(text), exclusive=False)

    async def _handle_input(self, text: str) -> None:
        """Async dispatch via tui_bridge."""
        from armance.service.tui_bridge import dispatch_input, agent_label, load_user_agents

        chat = self.query_one(ChatView)

        # Local copy command — handled before service dispatch
        stripped = text.strip()
        if stripped.startswith("/copy"):
            self._handle_copy_command(stripped)
            return

        if self._loop_ctx is None:
            chat.append_message("error", "service layer unavailable", label="error")
            return

        # Show thinking indicator in bottom-left.
        # Pick a label that hints at long-running ingestion when the user
        # explicitly invokes /library index / /ingest-docs / scan+index intents.
        try:
            from armance.nls import t as _t
            label = None
            low = stripped.lower()
            if (
                low.startswith("/library index")
                or low.startswith("/library scan")
                or low.startswith("/ingest-docs")
                or low.startswith("/ingest_docs")
                or low.startswith("/scan")
            ):
                label = _t("thinking.indexing")
            elif low.startswith("/library load") or low.startswith("/load"):
                label = _t("thinking.loading")
            thinking = self.query_one(ThinkingIndicator)
            thinking.show(label)
        except Exception:
            pass

        # Track this worker so the spinner survives agent switches.
        working_name = self.state.current_agent or "unknown"
        self._active_workers[working_name] = self._active_workers.get(working_name, 0) + 1
        self._refresh_sidebar(working_agent=working_name)

        # If the input is likely to trigger a Malik hand-off, mark her working
        # too — the user sees the spinner travel from Armance to Malik.
        try:
            sidebar = self.query_one(Sidebar)
            if self._likely_triggers_malik(text):
                sidebar.set_meta_state("system-hr", "working")
            if working_name and working_name.startswith("system-"):
                sidebar.set_meta_state(working_name, "working")
        except Exception:
            pass

        try:
            reply, agent_name = await dispatch_input(text, self._loop_ctx)
        except Exception as exc:
            logger.exception("dispatch failed")
            chat.append_message("error", f"dispatch error: {exc}", label="error")
            self._active_workers[working_name] = max(0, self._active_workers.get(working_name, 1) - 1)
            self._refresh_sidebar()
            if not any(v > 0 for v in self._active_workers.values()):
                try:
                    self.query_one(ThinkingIndicator).hide()
                except Exception:
                    pass
            return

        # Decrement worker count for this agent now that the response arrived.
        self._active_workers[working_name] = max(0, self._active_workers.get(working_name, 1) - 1)

        # Special markers
        if reply == "[quit]":
            if not any(v > 0 for v in self._active_workers.values()):
                try:
                    self.query_one(ThinkingIndicator).hide()
                except Exception:
                    pass
            self.app.exit(0)
            return
        if reply == "[clear]":
            chat.clear()
            if not any(v > 0 for v in self._active_workers.values()):
                try:
                    self.query_one(ThinkingIndicator).hide()
                except Exception:
                    pass
            self._refresh_sidebar()
            return

        # Format role label based on the responding agent
        label, role = agent_label(agent_name, self._loop_ctx.agents)
        chat.append_message(role, reply, label=label)

        # If the agent ended a line with @<MetaAgent>, ..., surface a hint
        # so the user knows they can hand the conversation off in one click.
        try:
            import re as _re
            mention = _re.search(r"^@(Malik|Kim|Mona|Armance|Serge)\b", reply, _re.MULTILINE)
            if mention and agent_name and not agent_name.endswith(mention.group(1).lower()):
                from armance.nls import t as _t
                hint = _t("agent_handoff.hint", target=mention.group(1))
                chat.append_message("system", hint, label="armance")
        except Exception:
            logger.debug("handoff hint surface failed", exc_info=True)

        # Hide thinking indicator only when ALL workers are done.
        if not any(v > 0 for v in self._active_workers.values()):
            try:
                self.query_one(ThinkingIndicator).hide()
            except Exception:
                pass

        # Clear meta working states only for agents that have no active worker.
        try:
            sidebar = self.query_one(Sidebar)
            still_working = {name for name, count in self._active_workers.items() if count > 0}
            sidebar.clear_meta_states(except_agents=still_working)
            # Heuristic: Malik's reply ending with a question = she awaits input
            if agent_name in ("system-hr", "hr") or "Malik" in (label or ""):
                if reply.rstrip().endswith("?"):
                    sidebar.set_meta_state("system-hr", "waiting")
            if agent_name in ("system-context", "context") or "Armance" in (label or ""):
                if reply.rstrip().endswith("?"):
                    sidebar.set_meta_state("system-context", "waiting")
            # Re-mark still-working agents so their spinner stays visible.
            for name in still_working:
                if name.startswith("system-"):
                    sidebar.set_meta_state(name, "working")
        except Exception:
            pass

        # Reload agents in case a recruitment created new ones, then refresh
        # the sidebar with the (possibly updated) active agent.
        try:
            self._loop_ctx.agents = load_user_agents(self.armance_root)
        except Exception:
            logger.exception("agent reload failed")
        self._refresh_sidebar(working_agent=next(
            (name for name, count in self._active_workers.items()
             if count > 0 and not name.startswith("system-")), None
        ))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_hitl_banner(self, agent_name: str | None = None) -> None:
        banner = self.query_one(HITLBanner)
        if agent_name:
            banner.show_for(agent_name)
        else:
            banner.hide()

    def append_chat_message(self, role: str, content: str, label: str | None = None) -> None:
        self.query_one(ChatView).append_message(role, content, label=label)
