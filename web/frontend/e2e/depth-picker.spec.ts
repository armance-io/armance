import { test, expect } from "@playwright/test";

test.describe("DepthPicker Workflow Launch E2E", () => {
  test("toggles launch configuration options and successfully submits run request", async ({ page }) => {
    let requestBody: any = null;

    // Mock workflows list so the DepthPicker renders (workflow exists)
    await page.route(
      "**/api/projects/*/sessions/*/workflows",
      async (route) => {
        if (route.request().method() === "GET" && !route.request().url().includes("/run")) {
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

    // Intercept launch POST request
    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/run",
      async (route) => {
        const req = route.request();
        if (req.method() === "POST") {
          requestBody = req.postDataJSON();
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ run_id: "run-mock-123" }),
        });
      }
    );

    // Navigate to the workflow launcher page
    await page.goto("/projects/default/sessions/session-1/workflows/my-workflow");

    // 1. Verify workflow name title displays
    await expect(page.getByRole("heading", { name: "my-workflow" }).first()).toBeVisible();

    // 2. Select the "Thorough, challenged analysis" (deep) card
    const deepCard = page.getByRole("radio", { name: "A thorough, challenged analysis" });
    await expect(deepCard).toBeVisible();
    await deepCard.click();
    await expect(deepCard).toHaveAttribute("aria-checked", "true");

    // 3. Switch mode from interactive to autonomous
    const autonomousBtn = page.getByRole("radio", { name: "autonomous" });
    await expect(autonomousBtn).toBeVisible();
    await autonomousBtn.click();
    await expect(autonomousBtn).toHaveAttribute("aria-checked", "true");

    // 4. Verify autonomous mode instruction hint is shown
    await expect(page.locator("text=Mona operates autonomous checkpoints to deliver the synthesis.")).toBeVisible();

    // 5. Click the Launch button
    const launchBtn = page.getByRole("button", { name: "Launch" });
    await expect(launchBtn).toBeVisible();
    await launchBtn.click();

    // 6. Verify intercepted payload values
    expect(requestBody).toEqual({
      mode: "autonomous",
      depth: "deep",
    });

    // 7. Assert that success status renders on page
    const statusDiv = page.locator("[data-testid='launch-status']");
    await expect(statusDiv).toContainText("Run launched: run-mock-123");
  });
});
