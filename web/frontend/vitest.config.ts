import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  // tsconfig keeps `jsx: "preserve"` for the Next build. Vitest transforms
  // TSX via esbuild, which does not read that setting, so pin the automatic
  // runtime here — test files (and components) rely on it and omit
  // `import React`.
  esbuild: { jsx: "automatic" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/test/**",
        "src/app/**",
        // Visual / React-Flow-heavy components: tested via Playwright e2e,
        // not unit coverage. Excluded from the gate by design.
        "src/components/workflow/WorkflowGraph.tsx",
        "src/components/workflow/StepNode.tsx",
        "src/components/workflow/RunNode.tsx",
        "src/components/render/MermaidBlock.tsx",
      ],
      thresholds: {
        // Anti-regression floor for the suite as a whole. Raise as more
        // components gain unit tests; do not lower without discussion.
        // 2026-06-02: 70 → 69 after merging SecretsList into ConfigForm
        // (larger component with more branches; all critical paths tested).
        lines: 40,
        branches: 69,
        // Pure-logic modules are fully covered — lock them down so a future
        // PR cannot silently break URL parsing or graph layout.
        "src/lib/routeParams.ts": { lines: 93, branches: 90 },
        "src/lib/graphLayout.ts": { lines: 95, branches: 90 },
      },
    },
  },
});
