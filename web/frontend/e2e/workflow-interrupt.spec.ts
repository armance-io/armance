import { test, expect } from "@playwright/test";

test.describe("Workflow Live Interruption E2E", () => {
  test("allows active workflow runs to be interrupted with popover confirmation", async ({ page }) => {
    // 1. Mock active workflow state showing run-1 is currently running
    await page.route(
      "**/api/projects/*/sessions/*/active-workflow",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            active: {
              workflow: "my-workflow",
              run_id: "run-1",
              manifest_path: "manifest.json",
            },
          }),
        });
      }
    );

    // Mock live manifest return showing running status
    const mockManifest = {
      run_id: "run-1",
      workflow: "my-workflow",
      status: "running",
      started_at: "2026-05-29T15:00:00Z",
      ended_at: null,
      steps: [],
    };

    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs/run-1",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            "manifest.json": JSON.stringify(mockManifest),
          }),
        });
      }
    );

    // Intercept mock runs history list
    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([]),
        });
      }
    );

    // 2. Intercept POST stop workflow route
    let stopCalled = false;
    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/stop",
      async (route) => {
        expect(route.request().method()).toBe("POST");
        expect(route.request().postDataJSON()).toEqual({ confirm: true });
        stopCalled = true;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ status: "stopped" }),
        });
      }
    );

    // Navigate to workflow launcher screen
    await page.goto("/projects/default/sessions/session-1/workflows/my-workflow");

    // Verify interrupt button is visible and active
    const interruptBtn = page.getByRole("button", { name: /interrupt/i });
    await expect(interruptBtn).toBeVisible();
    await expect(interruptBtn).toBeEnabled();

    // Click trigger button to launch inline confirmation popover
    await interruptBtn.click();

    // Verify confirmation modal prompt and buttons are visible
    const popover = page.locator('[role="alertdialog"]');
    await expect(popover).toBeVisible();
    await expect(popover).toContainText(/interrupt/i);

    // Confirm interruption by clicking yes
    const yesBtn = popover.getByRole("button", { name: /yes/i });
    await expect(yesBtn).toBeVisible();
    await yesBtn.click();

    // Verify the popover closes and backend route is invoked
    await expect(popover).not.toBeVisible();
    expect(stopCalled).toBe(true);
  });
});
