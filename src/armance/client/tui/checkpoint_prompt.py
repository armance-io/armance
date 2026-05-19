"""Terminal/TUI implementation of CheckpointHandler.

Handles three checkpoint kinds:
  - text   : free-form input via prompt_toolkit (Esc aborts)
  - select : pick one from checkpoint.options["choices"] via questionary
  - confirm: yes/no via questionary, returns "yes" / "no"
"""
from __future__ import annotations

import asyncio
from typing import Any

from armance.service.checkpoint import Checkpoint, CheckpointAbort, CheckpointResponse


class TerminalCheckpointHandler:
    async def prompt(self, checkpoint: Checkpoint) -> CheckpointResponse:
        kind = getattr(checkpoint, "kind", "text") or "text"
        if kind == "select":
            return await self._prompt_select(checkpoint)
        if kind == "confirm":
            return await self._prompt_confirm(checkpoint)
        return await self._prompt_text(checkpoint)

    async def _prompt_select(self, cp: Checkpoint) -> CheckpointResponse:
        import questionary
        choices = list(cp.options.get("choices", []))
        if not choices:
            return CheckpointResponse(content="", is_abort=True)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: questionary.select(cp.prompt, choices=choices).ask()
        )
        if result is None:
            return CheckpointResponse(content="", is_abort=True)
        return CheckpointResponse(content=str(result))

    async def _prompt_confirm(self, cp: Checkpoint) -> CheckpointResponse:
        import questionary
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: questionary.confirm(cp.prompt).ask()
        )
        if result is None:
            return CheckpointResponse(content="", is_abort=True)
        return CheckpointResponse(content="yes" if result else "no")

    async def _prompt_text(self, cp: Checkpoint) -> CheckpointResponse:
        prompt_text = cp.prompt or "Human checkpoint — provide your input:"
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.formatted_text import HTML
            from prompt_toolkit.key_binding import KeyBindings
            from prompt_toolkit.patch_stdout import patch_stdout
            from prompt_toolkit.styles import Style

            kb = KeyBindings()

            @kb.add("escape")
            def _esc_exit(event: Any) -> None:
                event.app.exit(exception=CheckpointAbort(), status=None)

            style = Style.from_dict({"prompt": "ansiblue bold"})
            session = PromptSession(
                style=style, key_bindings=kb, multiline=True, complete_while_typing=False,
            )
            try:
                with patch_stdout():
                    user_text: str = await session.prompt_async(
                        HTML(f"<prompt>CHECKPOINT [{cp.id}]:</prompt> {prompt_text}\n> "),
                        multiline=True,
                    )
            except CheckpointAbort:
                raise
            except (KeyboardInterrupt, EOFError):
                raise CheckpointAbort()
            return CheckpointResponse(content=user_text.strip())
        except ImportError:
            loop = asyncio.get_event_loop()
            print(f"\nCHECKPOINT [{cp.id}]: {prompt_text}")
            try:
                user_text = await loop.run_in_executor(None, input, "> ")
            except (KeyboardInterrupt, EOFError):
                raise CheckpointAbort()
            return CheckpointResponse(content=user_text.strip())
