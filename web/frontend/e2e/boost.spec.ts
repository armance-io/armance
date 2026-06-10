import { test, expect } from "./fixtures";

test.describe("Agent Boost E2E", () => {
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

    // Mock Agents API with one boosted specialist
    await page.route("**/api/projects/*/sessions/*/agents", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            name: "Armance",
            slug: "system-context",
            domain: "host",
            role: "host",
            provider: "openrouter",
            model: "gpt-4o",
            reasoning: "low",
            staff: true,
            boosted: false,
            effective_model: "gpt-4o",
          },
          {
            name: "Sara",
            slug: "Sara",
            domain: "helper",
            role: "helper",
            provider: "openrouter",
            model: "anthropic/claude-3.5-sonnet",
            reasoning: null,
            staff: false,
            boosted: true,
            effective_model: "anthropic/claude-opus-4-5",
          },
        ]),
      });
    });

    // Mock Session state API
    await page.route("**/api/projects/*/sessions/session-1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          state: {
            current_agent: "system-context",
          },
          agents: [
            { name: "Armance", first_name: "Armance", title: "host" },
            { name: "Sara", first_name: "Sara", title: "helper" },
          ],
          language: "en",
        }),
      });
    });

    // Mock active session messages
    await page.route("**/api/projects/*/sessions/*/messages", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    // Mock stats
    await page.route("**/api/projects/*/admin/stats", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          agents: {},
          global: { tokens_in: 0, tokens_out: 0, cost_usd: 0.0, msg_count: 0 },
        }),
      });
    });

    // Mock library
    await page.route("**/api/projects/*/sessions/*/library", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ read: [], unindexed: [] }),
      });
    });
  });

  test("displays effective model and glows header when active agent is boosted", async ({ page }) => {
    // Navigate to session
    await page.goto("/projects/default/sessions/session-1");

    // Initially active agent should be Armance, showing model gpt-4o
    const headerModel = page.getByTestId("header-model");
    await expect(headerModel).toBeVisible();
    await expect(headerModel).toContainText("gpt-4o");

    // Header element should NOT have the glow class initially
    const header = page.locator("header");
    await expect(header).not.toHaveClass(/ae-header-boost-glow/);

    // Switch to Sara (the boosted helper agent)
    // Sara is a specialist/recruit agent. In the sidebar we click Sara.
    const agentBtn = page.getByRole("button", { name: "Sara" });
    await expect(agentBtn).toBeVisible();
    await agentBtn.click();

    // Now model name should update to the effective boosted model (Opus)
    await expect(headerModel).toContainText("anthropic/claude-opus-4-5");

    // Header element should now have the glow class `.ae-header-boost-glow`
    await expect(header).toHaveClass(/ae-header-boost-glow/);
  });
});
