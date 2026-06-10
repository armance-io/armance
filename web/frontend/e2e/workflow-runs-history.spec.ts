import { test, expect } from "./fixtures";

test.describe("Workflow Runs History E2E", () => {
  test("displays historical runs, allows navigating, deleting completed runs, and blocks active deletions", async ({ page }) => {
    // Mock workflows list so the launcher renders (workflow exists)
    await page.route(
      "**/api/projects/*/sessions/*/workflows",
      async (route) => {
        if (route.request().method() === "GET" && !route.request().url().includes("/runs")) {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ workflows: [{ name: "my-workflow", scope: "", step_count: 1 }] }),
          });
        } else {
          await route.continue();
        }
      }
    );

    // 1. Mock active workflow run is idle
    await page.route(
      "**/api/projects/*/sessions/*/active-workflow",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ active: null }),
        });
      }
    );

    // Mock runs list showing:
    // - run-1: status: running (deletion blocked)
    // - run-2: status: completed (deletable)
    const mockRunsList = [
      {
        run_id: "run-1",
        status: "running",
        started_at: "2026-05-29T15:00:00Z",
        ended_at: null,
        duration_ms: 120000,
        tokens_total: 1500,
      },
      {
        run_id: "run-2",
        status: "completed",
        started_at: "2026-05-28T10:00:00Z",
        ended_at: "2026-05-28T10:05:00Z",
        duration_ms: 300000,
        tokens_total: 4500,
      },
    ];

    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockRunsList),
        });
      }
    );

    // Mock delete run endpoint
    let deleteCalled = false;
    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs/run-2",
      async (route) => {
        expect(route.request().method()).toBe("DELETE");
        deleteCalled = true;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ deleted: "run-2" }),
        });
      }
    );

    // Navigate to workflow launcher screen
    await page.goto("/projects/default/sessions/session-1/workflows/my-workflow");

    // 2. Verify sidebar contains the workflow name header and both runs
    const sidebar = page.locator("aside");
    await expect(sidebar.locator("text=my-workflow")).toBeVisible();

    const historySection = sidebar.locator("#run-history-list");
    await expect(historySection).toBeVisible();

    const row1 = historySection.locator('.run-row[aria-label*="run-1"]');
    const row2 = historySection.locator('.run-row[aria-label*="run-2"]');
    await expect(row1).toBeVisible();
    await expect(row2).toBeVisible();

    // 3. Verify delete button on active run-1 is disabled (aria-disabled=true)
    const deleteBtn1 = row1.locator("button.delete-trigger");
    await expect(deleteBtn1).toHaveAttribute("aria-disabled", "true");

    // 4. Verify completed run-2 can trigger deletion confirmation
    const deleteBtn2 = row2.locator("button.delete-trigger");
    await expect(deleteBtn2).toBeEnabled();
    await deleteBtn2.click();

    const deletePopover = row2.locator(".delete-popover");
    await expect(deletePopover).toBeVisible();
    await expect(deletePopover).toContainText(/delete/i);

    const yesBtn = deletePopover.locator(".delete-btn-yes");
    await yesBtn.click();

    // Verify deletion endpoint is called
    await expect(deletePopover).not.toBeVisible();
    expect(deleteCalled).toBe(true);
  });
});
