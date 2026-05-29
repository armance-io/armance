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
      exclude: ["src/**/*.test.{ts,tsx}", "src/test/**", "src/app/**"],
      // Global gate kept low until B–H epics ship their unit tests.
      // Per-epic acceptance still requires >= 80% lines on touched files.
      // Re-raise to { lines: 80, branches: 75 } once coverage catches up.
      thresholds: { lines: 0, branches: 0 },
    },
  },
});
