import { defineConfig, devices } from "@playwright/test";

// CI builds the app once (the "Lint + build frontend" step), so E2E serves the
// production bundle via `next start` — far faster than `pnpm dev`, which
// recompiles every route on first hit and made the suite take ~18 min.
const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  // One retry catches a genuine flake without tripling the run on a real
  // failure (the old value of 2 multiplied a broken suite's wall time by 3).
  retries: isCI ? 1 : 0,
  // Parallelise across CPUs in CI instead of running serially.
  workers: isCI ? "50%" : undefined,
  reporter: isCI ? "line" : "html",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    // Local dev keeps hot-reload via `pnpm dev`; CI serves the prebuilt bundle.
    command: isCI ? "pnpm start" : "pnpm dev",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: !isCI,
    timeout: 120_000,
  },
});
