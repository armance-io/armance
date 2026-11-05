---
governs: [src/armance/core/models/preset.py, src/armance/service/preset_ops.py, src/armance/service/preset_bench.py,
  src/armance/cli_preset.py, src/armance/assets/presets/, scripts/bench_presets.py]
depends: [workflow-engine, library-rag]
---
# presets

Turnkey domain packs (`armance preset list|show|apply`) and their replayable bench. A pack is pure data: a manifest,
workflows, role sheets, knowledge and bench cases. Applying it only drops files where existing mechanisms already read
them (workflows dir, library docs). The bench replays each case through the real recruitment and workflow engine and
has a judge from another model family compare the output, blind, with a frontier reference.

Constraints and non-goals:

- The engine never branches on a domain: no `if domain == ...` anywhere outside the pack's data.
- Apply is offline, idempotent and non-destructive: a differing existing file is reported as a conflict, never
  overwritten. Indexing stays an explicit `/library index`.
- User packs in the global `presets/` directory shadow the builtin ones.
- The live bench needs provider quota; only its offline logic is tested.

Criteria:

- A pack loads, a broken one is skipped in a listing, a user pack shadows a builtin:
  [test_load_ok](../../tests/test_presets.py), [test_discover_skips_broken](../../tests/test_presets.py),
  [test_discover_shadowing](../../tests/test_presets.py).
- Applying twice changes nothing, and never overwrites:
  [test_apply_then_reapply_idempotent](../../tests/test_presets.py), [test_apply_never_overwrites](../../tests/test_presets.py).
- The judge sees anonymised A and B in random order, and its verdict maps back to the right side:
  [test_judge_prompt_is_blind](../../tests/test_preset_bench.py),
  [test_both_sides_reachable_and_mapping_correct](../../tests/test_preset_bench.py),
  [test_verdict_deanonymised_to_reference](../../tests/test_preset_bench.py).
- The report shows the delta against the previous run: [test_render_with_delta](../../tests/test_preset_bench.py).
