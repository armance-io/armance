---
governs: [src/armance/service/handlers.py, src/armance/service/chat_handlers/, src/armance/service/tui_bridge.py,
  src/armance/service/checkpoint.py]
depends: [agents-staff, workflow-engine]
---
# chat-dispatch

Routes each user turn (slash command, `@Name` switch or free text) to its handler, sends free text to the current
staff shell (Armance, Malik, Kim, Mona, Serge) or to a recruited specialist, and owns the checkpoint contract
(`CheckpointHandler`) through which the service layer asks the human for input, whatever the frontend.

Constraints and non-goals:

- Switching agent is explicit, `@Name` only: no guessing from verbs ("talk to", "passe-moi"), they matched too much.
- Shells hold no heavy logic: they delegate to the agent services and intercept only `[EXECUTE:/...]` tags.
- The service layer never calls `input()`: every question to the human goes through a `CheckpointHandler`, the same
  for the TUI and the web. The handler knows kind, prompt and options; the frontend decides how it looks.
- An unknown command answers with the translated `dispatch.unknown_command` message, never a crash (checked by hand).

Criteria:

- `@Name` at the start of a message switches agent; a sentence that only names someone does not:
  [test_detect_switch_at_mention](../../tests/unit/service/test_tui_bridge.py),
  [test_detect_switch_nl_french_no_longer_matches](../../tests/unit/service/test_tui_bridge.py),
  [test_detect_switch_addressing_someone_in_third_person](../../tests/unit/service/test_tui_bridge.py).
- Staff files never load as recruited specialists:
  [test_load_user_agents_skips_system](../../tests/unit/service/test_tui_bridge.py).
- `dispatch_input` is the single entry point clients call:
  [test_dispatch_input_is_the_public_entry_point](../../tests/architecture/test_no_dead_facade.py).
- A human checkpoint without a handler fails loudly instead of blocking on stdin:
  [test_checkpoint_handler_required](../../tests/unit/core/models/test_workflow.py).
