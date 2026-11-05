---
governs: [src/armance/client/tui/]
depends: [chat-dispatch]
---
# tui-client

The terminal interface, built on Textual: the multi-agent conversation, the roster, the workflow pipeline and the
human-in-the-loop banner, in a warm editorial theme. It is a client: it never calls an LLM, it sends input to the
service layer through `tui_bridge.dispatch_input` and renders the events it gets back.

Constraints and non-goals:

- No orchestration and no claim checking here: the TUI shows claim density and the pipeline, it does not compute them.
- Terminal glyphs only, no graphics. One `Session` per app.
- No authentication: that belongs to the web layer.
- The `armance` theme uses no pure white, black or bluish colour (checked by hand).

Criteria:

- The workflow DAG renders as top-down ASCII from step dicts:
  [test_dag_ascii_single_step](../../tests/unit/client/tui/test_workflow_view_full.py),
  [test_dag_ascii_chain](../../tests/unit/client/tui/test_workflow_view_full.py).
- The human-in-the-loop banner shows only while a checkpoint is active:
  [test_hitl_banner_show_and_hide_via_pilot](../../tests/unit/client/tui/test_widgets/test_footer.py).
- The sidebar spinner and state colours are defined once:
  [test_spinner_frames_present](../../tests/unit/client/tui/test_widgets/test_sidebar.py),
  [test_state_colors_mapping](../../tests/unit/client/tui/test_widgets/test_sidebar.py).
- `/switch` loads the named agent and explains its usage otherwise:
  [test_cmd_switch_loads_agent](../../tests/unit/client/tui/test_tui_loop.py),
  [test_cmd_switch_no_args_returns_usage](../../tests/unit/client/tui/test_tui_loop.py).
