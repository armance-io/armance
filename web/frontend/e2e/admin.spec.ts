import { test, expect } from "@playwright/test";

const ADMIN_URL = "/projects/default/admin";

test.describe("G.10 — Admin page tabs E2E", () => {
  test.beforeEach(async ({ page }) => {
    // Persistent SidebarNav + session-aware admin resolve the current session
    // via /sessions/latest; mock it so the Agents tab gets a sid.
    await page.route("**/api/projects/*/sessions/latest", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "sess-e2e" }),
      });
    });

    // Mock Config API
    await page.route("**/api/projects/*/admin/config", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          default_provider: "openrouter",
          default_model: "gpt-4o",
          budget_effort: "low",
          language: "en",
          judge_model: "mona-judge",
          log_level: "info",
        }),
      });
    });

    // Mock Secrets API
    await page.route("**/api/projects/*/admin/secrets", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { name: "OPENROUTER_API_KEY", value: "sk-or-v1-abcdef", set: true },
        ]),
      });
    });

    // Mock Logs API
    await page.route("**/api/projects/*/admin/logs*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          lines: [
            { timestamp: "2026-05-30T10:00:00Z", agent: "Armance", event: "response", message: "Hello user" },
          ],
          total: 1,
          cursor: null,
        }),
      });
    });

    // Mock Stats API
    await page.route("**/api/projects/*/admin/stats", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          agents: {
            Armance: { tokens_in: 120, tokens_out: 250, cost_usd: 0.003, msg_count: 2 },
          },
          global: { tokens_in: 120, tokens_out: 250, cost_usd: 0.003, msg_count: 2 },
        }),
      });
    });

    // Mock Agents API
    await page.route("**/api/projects/*/sessions/*/agents", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { name: "Armance", domain: "host", role: "host", provider: "openrouter", model: "gpt-4o", reasoning: "low" },
        ]),
      });
    });

    // Mock Providers API
    await page.route("**/providers", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          providers: {
            openrouter: [{ id: "gpt-4o", name: "gpt-4o" }],
          },
        }),
      });
    });
  });

  test("clicking Config tab renders ConfigForm", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.getByRole("tab", { name: /config/i }).click();
    await expect(page.getByTestId("config-form")).toBeVisible();
    await expect(page.getByRole("button", { name: "Save" })).toBeVisible();
  });

  test("clicking Secrets tab renders SecretsList", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.getByRole("tab", { name: /secrets/i }).click();
    await expect(page.getByTestId("secrets-list")).toBeVisible();
    await expect(page.getByText("OPENROUTER_API_KEY")).toBeVisible();
  });

  test("clicking Logs tab renders LogViewer", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.getByRole("tab", { name: /logs/i }).click();
    await expect(page.getByTestId("log-viewer")).toBeVisible();
    await expect(page.getByTestId("log-viewer").getByText("Armance").first()).toBeVisible();
  });

  test("clicking Stats tab renders StatsDashboard", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.getByRole("tab", { name: /stats|statistics/i }).click();
    await expect(page.getByTestId("stats-dashboard")).toBeVisible();
    await expect(page.getByTestId("stats-dashboard").getByText("Armance").first()).toBeVisible();
  });

  test("clicking Agents tab renders AgentEditor", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.getByRole("tab", { name: /agents/i }).click();
    await expect(page.getByTestId("agent-editor")).toBeVisible();
    await expect(page.getByTestId("agent-editor").getByText("Armance").first()).toBeVisible();
  });
});
