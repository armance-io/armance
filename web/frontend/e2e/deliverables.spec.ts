import { test, expect } from "@playwright/test";

const DELIVERABLES_URL = "/projects/default/sessions/session-1/deliverables";

test.describe("H.3 — Deliverables tab E2E", () => {
  test.beforeEach(async ({ page }) => {
    // Mock deliverables list API
    await page.route("**/api/projects/*/sessions/*/deliverables", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "exports/wf-a/run-1/synthesis.md",
            title: "Synthesis A",
            kind: "synthesis",
            format: "md",
            workflow: "wf-a",
            run_id: "run-1",
            created_at: "2026-05-24T15:30:00Z",
            starred: false,
          },
          {
            id: "exports/wf-a/run-1/report.pdf",
            title: "Report A",
            kind: "export",
            format: "pdf",
            workflow: "wf-a",
            run_id: "run-1",
            created_at: "2026-05-24T15:31:00Z",
            starred: true,
          },
        ]),
      });
    });

    // Mock specific deliverable text API
    await page.route("**/api/projects/*/sessions/*/exports/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/markdown",
        body: "# Synthesis A\nBeautiful content details.",
      });
    });

    // Mock star PATCH API
    await page.route("**/api/projects/*/sessions/*/deliverables/**/star", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "exports/wf-a/run-1/synthesis.md",
          title: "Synthesis A",
          kind: "synthesis",
          format: "md",
          workflow: "wf-a",
          run_id: "run-1",
          created_at: "2026-05-24T15:30:00Z",
          starred: true,
        }),
      });
    });
  });

  test("renders the sidebar and central reader with deliverables list", async ({ page }) => {
    await page.goto(DELIVERABLES_URL);

    // Verify sidebar title
    await expect(page.getByText("Deliverables").first()).toBeVisible();

    // Verify synthesis row is present
    await expect(page.getByText("Synthesis A")).toBeVisible();
    await expect(page.getByText("Report A")).toBeVisible();

    // The first item content is fetched and displayed in reader
    await expect(page.locator(".deliverable-reader").getByRole("heading", { name: "Synthesis A" }).first()).toBeVisible();
  });

  test("clicking a row updates selected deliverable", async ({ page }) => {
    await page.goto(DELIVERABLES_URL);
    
    // Click on Synthesis A to trigger details load
    await page.getByText("Synthesis A").click();
    await expect(page.locator(".deliverable-reader").getByRole("heading", { name: "Synthesis A" }).first()).toBeVisible();
  });
});
