"""Sidebar: Roles & Agents / Workflows / Tasks (right side).

Active agent is highlighted via [reverse] markup; working agents show a
rotating spinner glyph (UNI_DOTS4-style) instead of the static idle dot.
"""
from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Static

from armance.core.models.task import Task

logger = logging.getLogger(__name__)

# Spinner frames (Braille pattern, like swelljoe/spinner UNI_DOTS4)
_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_SPINNER_INTERVAL = 0.1  # seconds per frame

_STATE_ICONS: dict[str, str] = {
    "idle":    "○",
    "working": "⠋",   # animated below
    "waiting": "?",   # legacy
    "input-required": "?", # HITL — agent awaits user input
    "completed":    "✓",
    "error":   "✕",
}

_STATE_COLORS: dict[str, str] = {
    "idle":    "grey50",
    "working": "yellow",
    "waiting": "cyan",
    "input-required": "cyan",
    "completed":    "green",
    "error":   "red",
}

_META_COLORS = {
    "host":           "deep_pink2",     # Armance — must match chat._META_AGENT_COLORS["armance"]
    "recruiter":      "medium_purple1", # Malik  — must match chat._META_AGENT_COLORS["malik"]
    "operator":       "cyan",           # Kim  — must match chat._META_AGENT_COLORS["kim"]
    "vice-president": "yellow",         # Mona  — must match chat._META_AGENT_COLORS["mona"]
}


def get_agent_color(name: str, role_val: str | None = None) -> str:
    label = f"{name} · {role_val}" if role_val else name
    colors = ["cyan", "magenta", "green", "dodger_blue1", "dark_orange", "deep_pink2", "medium_purple1", "turquoise2"]
    hash_val = sum(ord(c) for c in label)
    return colors[hash_val % len(colors)]


# Cost tier → pastille glyph + color (green=free, yellow=low/mid, red=high)
_COST_PASTILLE: dict[str, str] = {
    "free":   "[green]●[/]",
    "low":    "[yellow]●[/]",
    "medium": "[yellow]●[/]",
    "high":   "[red]●[/]",
}

# Rough heuristics: model id substrings → tier (no network call)
_MODEL_TIER_PATTERNS: list[tuple[str, str]] = [
    # Free / open-weight served free on OpenRouter
    (":free",    "free"),
    ("llama-3",  "low"),
    ("llama3",   "low"),
    ("mistral",  "low"),
    ("mixtral",  "low"),
    ("qwen",     "low"),
    ("gemma",    "free"),
    ("phi-",     "free"),
    # Mid-range
    ("gpt-4o-mini",   "low"),
    ("gpt-4o",        "medium"),
    ("claude-3-haiku","low"),
    ("claude-3-sonnet","medium"),
    ("claude-3-opus", "high"),
    ("claude-opus-4", "high"),
    ("claude-sonnet-4","medium"),
    ("claude-haiku-4", "low"),
    ("gemini-flash",  "low"),
    ("gemini-pro",    "medium"),
    # High-end
    ("o1",       "high"),
    ("o3",       "high"),
    ("gpt-4-turbo", "high"),
]


def model_cost_pastille(model: str | None) -> str:
    """Return a Rich-markup colored dot representing estimated model cost tier."""
    if not model:
        return "[grey50]●[/]"
    m = model.lower()
    for pattern, tier in _MODEL_TIER_PATTERNS:
        if pattern in m:
            return _COST_PASTILLE[tier]
    return "[grey50]●[/]"  # unknown → neutral



class SidebarSection(Widget):
    """Collapsible sidebar section with header + content area."""

    DEFAULT_CSS = """
    SidebarSection {
        height: auto;
        background: $panel;
        margin: 1 0 0 0;
    }

    SidebarSection > .section-header {
        height: 1;
        color: $accent;
        text-style: bold;
        padding: 0 2;
        background: $panel;
    }

    SidebarSection > .section-content {
        height: auto;
        color: $foreground-muted;
        padding: 0 2;
        background: $panel;
    }

    SidebarSection > .section-empty {
        height: 1;
        color: $foreground-disabled;
        padding: 0 2;
        background: $panel;
    }

    SidebarSection.collapsed > .section-content {
        display: none;
    }

    SidebarSection.collapsed > .section-empty {
        display: none;
    }
    """

    BINDINGS = [
        Binding("enter", "toggle", "Toggle section", show=False),
    ]

    def __init__(self, title: str, section_id: str, empty_hint: str = "—", **kwargs: Any) -> None:
        super().__init__(id=section_id, **kwargs)
        self._title = title
        self._empty_hint = empty_hint
        self._is_collapsed = False
        self._items: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static(self._title.upper(), classes="section-header")
        yield Static(self._empty_hint, classes="section-empty", id=f"{self.id}-empty")
        yield Static("", classes="section-content", id=f"{self.id}-content")

    def add_item(self, text: str) -> None:
        self._items.append(text)
        self._refresh()

    def set_items(self, items: list[str]) -> None:
        """Replace items wholesale — used by the spinner refresh tick."""
        self._items = list(items)
        self._refresh()

    def clear_items(self) -> None:
        self._items.clear()
        self._refresh()

    def _refresh(self) -> None:
        try:
            empty = self.query_one(f"#{self.id}-empty", Static)
            content = self.query_one(f"#{self.id}-content", Static)
        except Exception:
            return
        if not self._items:
            empty.styles.display = "block"
            content.update("")
        else:
            empty.styles.display = "none"
            content.update("\n".join(self._items))

    def action_toggle(self) -> None:
        self._is_collapsed = not self._is_collapsed
        self.set_class(self._is_collapsed, "collapsed")

    def jump_to(self) -> None:
        if self._is_collapsed:
            self._is_collapsed = False
            self.remove_class("collapsed")
        self.focus()
        self.scroll_visible()


class Sidebar(Widget):
    """Right-hand sidebar with Roles & Agents / Workflows / Tasks."""

    DEFAULT_CSS = """
    Sidebar {
        background: $panel;
        layout: vertical;
        overflow-y: auto;
        padding: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("0", "jump_meta", "Hosts", show=False),
        Binding("1", "jump_roles", "Roles", show=False),
        Binding("2", "jump_workflows", "Workflows", show=False),
        Binding("3", "jump_tasks", "Tasks", show=False),
    ]

    # Meta agents = Armance firm staff — fixed list, always visible
    _META_STAFF: list[tuple[str, str, str]] = [
        ("system-context",      "Armance", "host"),
        ("system-hr",           "Malik",   "recruiter"),
        ("system-orchestrator", "Kim",     "operator"),
        ("system-judge",        "Mona",    "vice-president"),
        ("system-challenger",   "Serge",   "criticalist"),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # State table: role -> [ {name, state, active} ]
        self._roles: dict[str, list[dict[str, Any]]] = {}
        self._workflows: list[dict[str, Any]] = []
        self._tasks: list[dict[str, Any]] = []
        self._active_meta: str | None = None  # canonical name of active meta agent
        # Meta-agent state map: canonical_name -> "idle" | "working" | "waiting"
        self._meta_states: dict[str, str] = {}
        # Meta-agent model map: canonical_name -> model string (for cost pastille)
        self._meta_models: dict[str, str] = {}
        self._spinner_idx: int = 0
        self._spinner_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        from armance.nls import t
        yield SidebarSection(
            t("sidebar.library"),
            section_id="section-library",
            empty_hint=t("sidebar.library_inactive"),
        )
        yield SidebarSection(
            t("sidebar.staff"),
            section_id="section-meta",
            empty_hint="—",
        )
        yield SidebarSection(
            t("sidebar.roles_agents"),
            section_id="section-roles",
            empty_hint=t("sidebar.no_agents"),
        )
        yield SidebarSection(
            t("sidebar.workflows"),
            section_id="section-workflows",
            empty_hint=t("sidebar.no_workflows"),
        )
        yield SidebarSection(
            t("sidebar.tasks"),
            section_id="section-tasks",
            empty_hint=t("sidebar.idle"),
        )

    def on_mount(self) -> None:
        # Start the spinner ticker — frames advance every _SPINNER_INTERVAL
        self._spinner_timer = self.set_interval(
            _SPINNER_INTERVAL, self._tick_spinner
        )
        # Render the meta-staff list (always present)
        self._render_meta()

    def _tick_spinner(self) -> None:
        self._spinner_idx = (self._spinner_idx + 1) % len(_SPINNER_FRAMES)
        if self._has_working_agents():
            self._render_roles()
        if self._has_working_meta():
            self._render_meta()
        
        # Always refresh tasks to keep icons moving
        if self._tasks:
            self.set_tasks(self._tasks)

    def _has_working_agents(self) -> bool:
        for items in self._roles.values():
            for it in items:
                if it.get("state") == "working":
                    return True
        return False

    def _has_working_meta(self) -> bool:
        return any(s == "working" for s in self._meta_states.values())

    # ------------------------------------------------------------------
    # Public API — declarative-ish: replace the agent set, render once.

    def set_agents(self, agents_by_role: dict[str, list[dict[str, Any]]]) -> None:
        """Set the full agent table.

        Args:
            agents_by_role: dict[role_name -> list[{"name": str, "state": str, "active": bool}]]
        """
        self._roles = agents_by_role
        self._render_roles()

    def update_agent_state(self, name: str, state: str) -> None:
        """Update a single agent's state without rebuilding the whole table."""
        for items in self._roles.values():
            for it in items:
                if it.get("name") == name:
                    it["state"] = state
        self._render_roles()

    def set_active_agent(self, name: str | None) -> None:
        """Mark a single agent as active (highlighted), unmark all others."""
        for items in self._roles.values():
            for it in items:
                it["active"] = (it.get("name") == name)
        self._active_meta = name
        self._render_roles()
        self._render_meta()

    def set_meta_models(self, models: dict[str, str]) -> None:
        """Update meta-agent model map for cost pastilles. canonical_name -> model."""
        self._meta_models.update(models)
        self._render_meta()

    def set_meta_state(self, canonical: str, state: str) -> None:
        """Set a meta agent's state (e.g. system-hr → "working" | "waiting" | "idle")."""
        self._meta_states[canonical] = state
        self._render_meta()

    def clear_meta_states(self, except_agents: set[str] | None = None) -> None:
        """Reset all meta states to idle, preserving any in except_agents."""
        if except_agents:
            self._meta_states = {k: v for k, v in self._meta_states.items() if k in except_agents}
        else:
            self._meta_states = {}
        self._render_meta()

    def _render_meta(self) -> None:
        try:
            section = self.query_one("#section-meta", SidebarSection)
        except Exception:
            return
        lines: list[str] = []
        for canonical, first_name, title in self._META_STAFF:
            is_active = (self._active_meta == canonical) or (self._active_meta == first_name)
            state = self._meta_states.get(canonical, "idle")
            label = f"{first_name:<10}"
            title_text = f"[grey50]{title}[/]"
            # Glyph by state
            color = _META_COLORS.get(title, "magenta")
            if state == "working":
                glyph = f"[yellow]{_SPINNER_FRAMES[self._spinner_idx]}[/]"
            elif state in ("waiting", "input-required"):
                glyph = "[cyan]?[/]"
            elif is_active:
                glyph = f"[{color}]●[/]"
            else:
                glyph = f"[{color}]·[/]"
            cost_dot = model_cost_pastille(self._meta_models.get(canonical))
            if is_active:
                line = f"  {glyph} [reverse bold]{label}[/] {title_text} {cost_dot}"
            else:
                line = f"  {glyph} [bold]{label}[/] {title_text} {cost_dot}"
            lines.append(line)
        section.set_items(lines)

    def _render_roles(self) -> None:
        try:
            section = self.query_one("#section-roles", SidebarSection)
        except Exception:
            return
        # Filter out meta roles (system-* agents grouped under "meta" role)
        meta_roles = {"meta", "system", "staff"}
        lines: list[str] = []
        for role in self._roles.keys():
            if role.lower() in meta_roles:
                continue
            # Skip role if all members are system-* (defensive)
            members = [it for it in self._roles[role]
                       if not str(it.get("name", "")).startswith("system-")]
            if not members:
                continue
            lines.append(f"[bold]{role}[/]")
            for it in members:
                name = it.get("name", "?")
                state = it.get("state", "idle")
                active = it.get("active", False)
                persona = it.get("persona", "") or ""
                model = it.get("model") or None

                agent_color = get_agent_color(name, role)
                if state == "working":
                    icon = _SPINNER_FRAMES[self._spinner_idx]
                    color = "yellow"
                elif state in ("waiting", "input-required"):
                    icon = "?"
                    color = "cyan"
                elif state == "completed":
                    icon = "✓"
                    color = "green"
                elif state == "error":
                    icon = "✕"
                    color = "red"
                elif active:
                    icon = "●"
                    color = agent_color
                else:
                    icon = "·"
                    color = agent_color

                # Cost pastille based on model tier
                cost_dot = model_cost_pastille(model)

                # Truncate persona to keep row compact
                persona_disp = persona[:12]
                tag = f" [grey50]· {persona_disp}[/]" if persona_disp else ""
                if active:
                    line = f"  [{color}]{icon}[/] [reverse bold]{name}[/]{tag} {cost_dot}"
                else:
                    line = f"  [{color}]{icon}[/] {name}{tag} {cost_dot}"
                lines.append(line)
        section.set_items(lines)

    # ------------------------------------------------------------------
    # Workflows / Tasks (declarative replace)

    def set_workflows(self, workflows: list[dict[str, Any]]) -> None:
        self._workflows = workflows
        section = self.query_one("#section-workflows", SidebarSection)
        lines = []
        for w in workflows:
            marker = "[yellow]▶[/] " if w.get("working") else "  "
            lines.append(f"{marker}{w.get('name', '?')}")
        section.set_items(lines)

    def set_library(self, summary: dict) -> None:
        """Update the Library section from a library_availability.library_summary dict.

        summary keys: active(bool), provider(str), model(str), docs(int), chunks(int).
        """
        from armance.nls import t as _t
        section = self.query_one("#section-library", SidebarSection)
        if not summary.get("active"):
            section.set_items([_t("sidebar.library_inactive_line")])
            return
        provider = summary.get("provider", "")
        model = summary.get("model", "").split("/")[-1].replace(":free", "")
        docs = int(summary.get("docs", 0) or 0)
        chunks = int(summary.get("chunks", 0) or 0)
        section.set_items([
            _t("sidebar.library_active_line",
               provider=provider, model=model, docs=docs, chunks=chunks),
        ])

    def set_tasks(self, tasks: list[Task]) -> None:
        self._tasks = tasks
        section = self.query_one("#section-tasks", SidebarSection)
        lines = []
        for t in tasks:
            if t.state == "working":
                icon = f"[yellow]{_SPINNER_FRAMES[self._spinner_idx]}[/]"
            elif t.state == "completed":
                icon = "[green]✓[/]"
            elif t.state == "failed":
                icon = "[red]✕[/]"
            elif t.state == "input-required":
                icon = "[cyan]?[/]"
            else:
                icon = "[grey50]·[/]"

            prompt_snip = t.prompt[:15] + ("..." if len(t.prompt) > 15 else "")
            lines.append(f"{icon} {prompt_snip} [grey50]{t.state}[/]")
        section.set_items(lines)

    # ------------------------------------------------------------------
    # Imperative API (used by handlers)

    def add_agent(self, role: str, name: str, state: str, active: bool = False) -> None:
        self._roles.setdefault(role, []).append(
            {"name": name, "state": state, "active": active}
        )
        self._render_roles()

    def add_role_header(self, role: str) -> None:
        # No-op: role headers are derived from set_agents()
        self._roles.setdefault(role, [])
        self._render_roles()

    def add_workflow(self, name: str, running: bool = False) -> None:
        self._workflows.append({"name": name, "working": running})
        self.set_workflows(self._workflows)

    def add_task(self, task_id: str, status: str) -> None:
        self._tasks.append({"id": task_id, "status": status})
        self.set_tasks(self._tasks)

    def clear_agents(self) -> None:
        self._roles = {}
        self._render_roles()

    def clear_workflows(self) -> None:
        self._workflows = []
        self.set_workflows([])

    def clear_tasks(self) -> None:
        self._tasks = []
        self.set_tasks([])

    # ------------------------------------------------------------------
    # Navigation actions

    def jump_to_section(self, name: str) -> None:
        section_id = f"section-{name}"
        try:
            self.query_one(f"#{section_id}", SidebarSection).jump_to()
        except Exception:
            logger.debug("jump_to_section: section %r not found", name)

    def action_jump_meta(self) -> None:
        self.jump_to_section("meta")

    def action_jump_roles(self) -> None:
        self.jump_to_section("roles")

    def action_jump_workflows(self) -> None:
        self.jump_to_section("workflows")

    def action_jump_tasks(self) -> None:
        self.jump_to_section("tasks")
