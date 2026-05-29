/**
 * EI.8 Playwright spec — footprint chip + Empreinte admin tab.
 *
 * STATUS: fixme — blocked on two dependencies:
 *   1. Visual components (FootprintChip, FootprintTab, Méthode expander)
 *      must be generated via web-v2-claude-design-prompts.md and wired in.
 *   2. Live header chip blocked on Epic C (SSE ledger-snapshot channel).
 *
 * Remove fixme annotations and fill assertions when Design hand-off is done
 * and Epic C's SSE ledger event is wired.
 */
import { test, expect } from "@playwright/test";

test.describe("EI.8 — Footprint chip + Empreinte admin tab", () => {
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

  test.fixme(
    "admin Empreinte tab renders per-agent gCO₂e rollup",
    async ({ page }) => {
      // Blocked: FootprintTab skeleton.
      // After Design: assert tab visible, agent rows present.
      await page.goto("/projects/default/admin");
      await page.getByRole("tab", { name: /empreinte/i }).click();
      await expect(page.getByTestId("footprint-tab")).toBeVisible();
    },
  );

  test.fixme(
    "Empreinte tab shows estimate badge for ~ rows",
    async ({ page }) => {
      await page.goto("/projects/default/admin");
      await page.getByRole("tab", { name: /empreinte/i }).click();
      await expect(page.getByTestId("estimate-badge")).toBeVisible();
    },
  );

  test.fixme(
    "Méthode expander cites EcoLogits + ISO 14044",
    async ({ page }) => {
      await page.goto("/projects/default/admin");
      await page.getByRole("tab", { name: /empreinte/i }).click();
      await page.getByRole("button", { name: /méthode/i }).click();
      await expect(page.getByTestId("methode-panel")).toContainText("EcoLogits");
      await expect(page.getByTestId("methode-panel")).toContainText("ISO 14044");
    },
  );
});
