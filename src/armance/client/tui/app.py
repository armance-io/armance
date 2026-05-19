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
# Armance theme — professional, monochromatic blue with single accent
# ---------------------------------------------------------------------------

ARMANCE_THEME = Theme(
    name="armance",
    primary="#58A6FF",          # blue accent (links, focus)
    secondary="#7EE787",        # subtle green (success states)
    accent="#F0B040",           # warm amber (highlights, /commands)
    foreground="#E6EDF3",       # primary text
    background="#0D1117",       # deep dark base
    surface="#161B22",          # input fields, hovered rows
    panel="#1A1F26",            # sidebar, headers, footers
    success="#7EE787",
    warning="#F0B040",
    error="#FF7B72",
    boost="#FFFFFF12",
    dark=True,
    variables={
        # Custom variants (optional, used by some themed widgets)
        "footer-key-foreground": "#58A6FF",
        "scrollbar": "#2A3038",
        "scrollbar-hover": "#58A6FF",
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
