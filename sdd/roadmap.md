# Roadmap

The order of the work, one line and one link per change. Coarse, not a sprint board.

## Now

1. Serge cross-family on the auto-invoke path, the last hole in the first pillar:
   [serge-cross-family-not-enforced-on-autoinvoke](issues/serge-cross-family-not-enforced-on-autoinvoke.md).
2. Run the preset bench live once, and measure the Creuset against the manual pipeline:
   [bench-first-live-run](issues/bench-first-live-run.md).
3. One model registry for discovery, families and footprint: [model-registry](issues/model-registry.md).
4. Split `cli.py` and `handlers.py` before they grow again: [split-big-files](issues/split-big-files.md).

## Next: the doctrine (decision 2)

5. Memory of disagreements: [disagreement-memory](issues/disagreement-memory.md).
6. Reasoning receipt export, cheap and early: [reasoning-receipt-export](issues/reasoning-receipt-export.md).
7. Global config page and root-level budgets: [global-config](issues/global-config.md).
8. Carbon budget as a constraint: [carbon-budget-governance](issues/carbon-budget-governance.md).
9. Local inference as a provider: [local-inference-ollama](issues/local-inference-ollama.md).
10. Sovereign projects by network allowlist: [sovereign-mode-allowlist](issues/sovereign-mode-allowlist.md).

## Known bugs

- [launcher-token-in-url](issues/launcher-token-in-url.md)
- [provider-rate-limit-during-background-run](issues/provider-rate-limit-during-background-run.md)
- [spinner-spins-without-tokens](issues/spinner-spins-without-tokens.md)
- [parallel-lanes-not-rendered](issues/parallel-lanes-not-rendered.md)
- [sidebar-tasks-dead-section](issues/sidebar-tasks-dead-section.md)
- [switch-ack-historical-heuristic](issues/switch-ack-historical-heuristic.md)
- [scrubber-fr-only](issues/scrubber-fr-only.md)

## Later

- Library freshness, replace, date and signal (decision 9): [rag-versioning-temporality](issues/rag-versioning-temporality.md).
- Embedding model proposed from the documents: [auto-embed-discovery](issues/auto-embed-discovery.md).
- Tool-based library retrieval: [library-adaptive-retrieval](issues/library-adaptive-retrieval.md).
- Pipeline view and background runs in the TUI: [workflow-live-pipeline](issues/workflow-live-pipeline.md).
- Kim before Malik in the flow: [reorder-host-kim-malik-flow](issues/reorder-host-kim-malik-flow.md).
- First-class forward tag between agents: [forward-tag-first-class](issues/forward-tag-first-class.md).
- Multimodal inputs and outputs: [multimodal-capabilities](issues/multimodal-capabilities.md).
- GitHub Copilot as a model source: [copilot-provider](issues/copilot-provider.md).
- Installable web app on mobile: [web-pwa-mobile](issues/web-pwa-mobile.md).

## Someday

- A contradictor chosen per decision type (decision 2, d), once the memory of disagreements is stable.
- Armance skills exposed as MCP tools; recruited specialists as A2A endpoints.
- OpenTelemetry spans on every LLM call, step and checkpoint.
- An OCI image for the local stack (one `docker run` on the user's own machine).
- A standalone binary (no pip) and a native window around the web UI.
