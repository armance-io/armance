import { test as base, expect } from "@playwright/test";

/**
 * Shared E2E fixture — seals the suite off from any real backend.
 *
 * Epic S added the auth gate: any API call answering 401 hard-redirects the
 * SPA to /login. Specs only mock the endpoints they care about, so every
 * unmocked call used to leak to the proxy target (a real, auth-gated
 * backend locally; a dead proxy in CI) and the whole suite bounced to the
 * login screen.
 *
 * This catch-all answers 404 for any /api call a spec did not mock —
 * the same "react-query error state, page still renders" behaviour the
 * suite was written against. Spec-level page.route registrations are
 * checked first by Playwright (last registered wins), so per-spec mocks
 * keep precedence.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route("**/api/**", (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "e2e_unmocked" }),
      }),
    );
    // A 404 on the session fetch triggers the stale-session recovery
    // (ChatStreamContainer redirects to /projects/{pid}), which would yank
    // every test off its page. Registered after the catch-all so it wins;
    // spec-level mocks, registered later still, override both.
    await page.route("**/api/projects/*/sessions/*", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "session-1", agents: [] }),
      }),
    );
    await use(page);
  },
});

export { expect };
