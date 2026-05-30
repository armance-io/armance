/**
 * G.10 Playwright spec — Admin page tabs.
 *
 * The Admin page at /projects/default/admin must render 5 tabs:
 * Config / Secrets / Logs / Stats / Agents. Each tab mounts the
 * corresponding component wired to the backend routes.
 *
 * STATUS: fixme — requires a running backend + seeded session.
 * Remove fixme annotations once the dev server is wired end-to-end.
 */
import { test, expect } from "@playwright/test";

const ADMIN_URL = "/projects/default/admin";

const TABS = ["Config", "Secrets", "Logs", "Stats", "Agents"] as const;

test.describe("G.10 — Admin page tabs", () => {
  for (const tab of TABS) {
    test.fixme(`admin page has a "${tab}" tab`, async ({ page }) => {
      await page.goto(ADMIN_URL);
      const tabEl = page.getByRole("tab", { name: new RegExp(tab, "i") });
      await expect(tabEl).toBeVisible();
    });
  }

  test.fixme("clicking Config tab renders ConfigForm", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.getByRole("tab", { name: /config/i }).click();
    await expect(page.getByTestId("config-form")).toBeVisible();
  });

  test.fixme("clicking Secrets tab renders SecretsList", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.getByRole("tab", { name: /secrets/i }).click();
    await expect(page.getByTestId("secrets-list")).toBeVisible();
  });

  test.fixme("clicking Logs tab renders LogViewer", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.getByRole("tab", { name: /logs/i }).click();
    await expect(page.getByTestId("log-viewer")).toBeVisible();
  });

  test.fixme("clicking Stats tab renders StatsDashboard", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.getByRole("tab", { name: /stats/i }).click();
    await expect(page.getByTestId("stats-dashboard")).toBeVisible();
  });

  test.fixme("clicking Agents tab renders AgentEditor", async ({ page }) => {
    await page.goto(ADMIN_URL);
    await page.getByRole("tab", { name: /agents/i }).click();
    await expect(page.getByTestId("agent-editor")).toBeVisible();
  });
});
