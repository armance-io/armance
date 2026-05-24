"""Textual App entry point for Armance TUI."""
from __future__ import annotations

import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.theme import Theme

from armance.config import Config
from armance.service.llm_service import TokenLedger
from armance.service.session import Session

from armance.client.tui.screens.main import MainScreen

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Armance theme — warm editorial palette
#
# Paper-ivory and warm-ink, transposed to a dark terminal: deep brown-ink
# background, cream foreground, rust accent, sage for active states.
# Never saturated, never bluish. Matches armance.io's published palette
# (oklch tokens converted to sRGB).
# ---------------------------------------------------------------------------

ARMANCE_THEME = Theme(
    name="armance",
    # Rust — warm primary accent (links, focus, scrollbar hover)
    primary="#e98667",
    # Sage — sober green for active / success states
    secondary="#5a8567",
    # Amber-of-passed-ink — for /commands and key highlights
    accent="#c5aa72",
    # Cream foreground, never pure white
    foreground="#eeebe4",
    # Deep warm ink — never a pure black, never bluish
    background="#15110d",
    # Panel cards (input fields, hovered rows)
    surface="#1e1a16",
    # Sidebar / header / footer body
    panel="#1e1a16",
    success="#5a8567",
    warning="#d9b06b",
    error="#c86459",
    boost="#eeebe408",
    dark=True,
    variables={
        "footer-key-foreground": "#c5aa72",
        "scrollbar": "#322d27",
        "scrollbar-hover": "#e98667",
    },
)


class ArmanceApp(App[int]):
    """Main Textual application for Armance TUI."""

    CSS_PATH = Path(__file__).parent / "themes" / "app.tcss"

    TITLE = "Armance"
    SUB_TITLE = "multi-agent strategic brain"

    def __init__(
        self,
        armance_root: Path,
        cfg: Config,
        session: Session,
        ledger: TokenLedger,
        theme: str = "armance",
    ) -> None:
        super().__init__()
        self.armance_root = armance_root
        self.cfg = cfg
        self.session = session
        self.state = session.state
        self.ledger = ledger
        self.theme_name = theme

    def compose(self) -> ComposeResult:
        return
        yield  # generator marker

    def on_mount(self) -> None:
        logger.info("ArmanceApp mounting, theme=%s", self.theme_name)
        # Register and apply Armance theme
        try:
            self.register_theme(ARMANCE_THEME)
            self.theme = "armance"
        except Exception:
            logger.exception("failed to apply armance theme")

        self.push_screen(
            MainScreen(
                armance_root=self.armance_root,
                cfg=self.cfg,
                session=self.session,
                ledger=self.ledger,
            )
        )


async def run_textual_tui(
    armance_root: Path,
    cfg: Config,
    session: Session,
    ledger: TokenLedger,
    theme: str = "armance",
) -> int:
    """Run the Textual TUI. Replaces run_tui() from tui_loop.py."""
    app = ArmanceApp(
        armance_root=armance_root,
        cfg=cfg,
        session=session,
        ledger=ledger,
        theme=theme,
    )
    result = await app.run_async()
    return result if isinstance(result, int) else 0
