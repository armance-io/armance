---
governs: [src/armance/core/models/workflow.py, src/armance/core/models/_workflow_prompts.py,
  src/armance/service/workflow_runs.py, src/armance/service/workflow_ascii.py, src/armance/service/workflow_yaml_writer.py,
  src/armance/service/workflow_crucible.py, src/armance/service/workflow_validation.py,
  src/armance/service/workflow_quality_report.py, src/armance/service/gate_parsing.py, src/armance/service/seed_docs.py,
  src/armance/service/skills/rerun_with_override.py]
depends: [core-models]
---
# workflow-engine

One engine: `execute_workflow`, a function over a YAML DAG (topological levels, steps of a level run concurrently),
with pre and post hooks injected by the caller. The Creuset runs a hard step as parallel drafts from different model
families, a critique, a revision and a rubric gate. Every run is versioned and auditable: prompts, warnings, costs and
a `quality.md` when the run holds Creuset steps.

Constraints and non-goals:

- The safety nets (cross-family check, Serge auto-invoke) are hooks of the service layer, not engine code.
- No revision loop: a Creuset iteration is a bounded static unrolling guarded by `run_if`, known at parse time, so the
  DAG stays checkable and replayable.
- No template engine: double-brace substitution only. `core` never reads the disk; seed docs and override files are
  read by the service and passed as inputs.
- A run never overwrites another; a rerun derives a new run and leaves its parent intact.
- `cost_usd` stays unset until a cost is measured: no estimate in its place.

Criteria:

- A cycle or an unknown dependency fails at parse time:
  [test_parse_rejects_cycle](../../tests/unit/core/models/test_workflow.py),
  [test_parse_rejects_unknown_dependency](../../tests/unit/core/models/test_workflow.py).
- Steps run by topological level: [test_execute_workflow_runs_in_topo_order](../../tests/unit/core/models/test_workflow.py).
- An abort cancels the sibling steps in flight: [test_abort_cancels_sibling_steps](../../tests/unit/service/test_workflow_p2_lot.py).
- A workflow without `stage` runs as before: [test_backward_compat_all_standard](../../tests/unit/core/models/test_workflow_crucible.py).
- A malformed or dangling `run_if` fails at parse time:
  [test_run_if_malformed_raises](../../tests/unit/core/models/test_workflow_crucible.py),
  [test_run_if_dangling_gate_raises](../../tests/unit/core/models/test_workflow_crucible.py),
  [test_run_if_references_non_gate_raises](../../tests/unit/core/models/test_workflow_crucible.py).
- A gate that accepts skips the revision as a pass-through; a gate without a verdict tag counts as REVISE:
  [test_gate_accept_skips_revision_passthrough](../../tests/unit/core/models/test_workflow_crucible.py),
  [test_gate_absent_tag_treated_as_revise](../../tests/unit/core/models/test_workflow_crucible.py).
- A run without Creuset steps has no quality report:
  [test_non_crucible_run_returns_none](../../tests/unit/service/test_workflow_quality_report.py).
- A rewritten workflow archives its previous version:
  [test_existing_workflow_is_archived](../../tests/integration/test_workflow_design_dialogue.py).
- A partial rerun replays the overridden step and what depends on it:
  [test_partial_rerun_end_to_end](../../tests/integration/test_workflow_rerun_override.py).
