---
governs: [src/armance/service/serge_ops.py, src/armance/service/workflow_hooks.py,
  src/armance/service/agents/challenger_agent.py]
depends: [agents-staff, workflow-engine]
---
# serge-adversarial

Serge is the mandatory contradictor, one of the three anti-lie mechanisms. His reason to exist is model diversity: he
runs on a model family different from the executors and from Mona, or his pushback is theatre, since a model of the
same family shares the same priors and agrees out of sycophancy. A soft consensus is a danger signal, not a success.

Constraints and non-goals:

- The family rule is a hard check where Serge is built, not a tone of voice.
- `validate_cross_family` before a run only warns: the workflow stays the user's choice.
- Serge writes no deliverable and saves no context.
- Known gap: the consensus auto-invoke does not re-check the family yet
  (`sdd/issues/serge-cross-family-not-enforced-on-autoinvoke.md`).

Criteria:

- Serge on the family of the executors or of Mona refuses to run:
  [test_cross_family_hard_refusal_single_provider](../../tests/unit/service/agents/test_challenger_agent.py),
  [test_cross_family_ok_different_providers](../../tests/unit/service/agents/test_challenger_agent.py).
- Diversity is judged by model family, not by provider name:
  [test_two_providers_same_family_still_single_family](../../tests/unit/service/test_workflow_hooks_family.py).
- One judge step with an empty Divergence section, and no critique step planned, brings Serge in once; no empty
  Divergence, no Serge:
  [test_single_empty_divergence_triggers_serge](../../tests/integration/test_serge_auto_invoke.py),
  [test_no_empty_divergence_no_auto_invoke](../../tests/integration/test_serge_auto_invoke.py),
  [test_e2e_post_run_hook_appends_auto_step](../../tests/integration/test_serge_auto_invoke.py).
- A critique without a real objection is marked inconclusive, never passed off as approval:
  [test_zero_objections_marks_serge_inconclusive](../../tests/unit/service/agents/test_challenger_agent.py).
