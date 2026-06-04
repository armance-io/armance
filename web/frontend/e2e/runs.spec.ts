import { test, expect } from "@playwright/test";

test.describe("Workflow Runs Detail E2E", () => {
  test("loads the run detail page and renders stats and steps", async ({ page }) => {
    const mockManifest = {
      run_id: "run-1",
      workflow: "my-workflow",
      status: "completed",
      started_at: "2026-05-29T15:00:00Z",
      ended_at: "2026-05-29T15:05:00Z",
      duration_ms: 300000,
      steps: [
        {
          id: "step-1",
          status: "completed",
          started_at: "2026-05-29T15:01:00Z",
          ended_at: "2026-05-29T15:02:00Z",
          duration_ms: 60000,
          tokens_in: 50,
          tokens_out: 100,
        },
      ],
      totals: {
        tokens_in: 50,
        tokens_out: 100,
        cost_usd: 0.0025,
      },
    };

    const mockFiles = {
      "manifest.json": JSON.stringify(mockManifest),
    };

    // Mock loadRun response
    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs/run-1",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockFiles),
        });
      }
    );

    // Mock loadStep response
    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs/run-1/step/step-1",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "text/plain",
          body: "# Step 1 Output markdown content",
        });
      }
    );

    // Navigate to the run detail page
    await page.goto("/projects/default/sessions/session-1/workflows/my-workflow/runs/run-1");

    // Verify main header and run status meta row
    const main = page.locator("main");
    await expect(main.locator("h2")).toContainText("my-workflow");
    await expect(main).toContainText("Duration: 300.0s");
    await expect(main).toContainText("Tokens: 150");
    await expect(main).toContainText("Cost: $0.0025");

    // Verify step list row renders
    const stepRow = page.locator('[aria-label="Step step-1"]');
    await expect(stepRow).toBeVisible();
    await expect(stepRow).toContainText("step-1");
    await expect(stepRow).toContainText("60.0s");

    // Verify step output markdown container is not visible initially
    await expect(page.locator("text=Step 1 Output markdown content")).not.toBeVisible();

    // Expand the step
    await stepRow.click();

    // Verify step output markdown fetches and is shown
    await expect(page.locator("text=Step 1 Output markdown content")).toBeVisible();
  });
});
