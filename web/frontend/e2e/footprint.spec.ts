/**
 * EI.8 Playwright spec — footprint chip + Empreinte admin tab.
 */
import { test, expect } from "@playwright/test";

const ADMIN_URL = "/projects/default/admin";

test.describe("EI.8 — Footprint chip + Empreinte admin tab", () => {
  test.beforeEach(async ({ page }) => {
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

    // Mock Footprint API
    await page.route("**/api/projects/*/admin/footprint?group_by=agent", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          by_agent: {
            Armance: {
              calls: 12,
              gco2e: 42.5,
              water_ml: 240,
              has_estimate: true,
              has_unknown: false,
            },
          },
          by_day: {},
          by_month: {},
          by_session: {},
          dominant_zone: "WOR",
        }),
      });
    });
  });

  test.fixme(
    "header shows 🌱 gCO₂e chip after a deliberation turn",
    async ({ page }) => {
      // Blocked: FootprintChip skeleton; Epic C SSE ledger channel missing.
      // After Design + Epic C: assert chip visible, value > 0.
      await page.goto("/projects/default/sessions/test");
      await expect(page.getByTestId("footprint-chip")).toBeVisible();
    },
  );

  test.fixme(
    "header chip shows ~ prefix when session has estimate entries",
    async ({ page }) => {
      await page.goto("/projects/default/sessions/test");
      await expect(page.getByTestId("footprint-chip")).toContainText("~");
    },
  );

  test.fixme(
    "header chip shows 🌱? when no footprint data available",
    async ({ page }) => {
      await page.goto("/projects/default/sessions/test");
      await expect(page.getByTestId("footprint-chip")).toContainText("?");
    },
  );

  // The Empreinte tab was merged into Statistics: footprint now renders in
  // the Stats dashboard, with the EcoLogits method note folded in there.
  test(
    "admin Statistics tab renders per-agent gCO₂e rollup",
    async ({ page }) => {
      await page.goto(ADMIN_URL);
      await page.getByRole("tab", { name: /statistics|statistiques/i }).click();
      await expect(page.getByTestId("stats-dashboard")).toBeVisible();
    },
  );

  test(
    "Statistics method expander cites EcoLogits + ISO 14044",
    async ({ page }) => {
      await page.goto(ADMIN_URL);
      await page.getByRole("tab", { name: /statistics|statistiques/i }).click();
      await page.getByRole("button", { name: /méthode|method/i }).click();
      await expect(page.getByTestId("methode-panel")).toContainText("EcoLogits");
      await expect(page.getByTestId("methode-panel")).toContainText("ISO 14044");
    },
  );
});
