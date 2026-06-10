import { test, expect } from "./fixtures";

test.describe("Workflow Graph Live E2E", () => {
  test("renders step nodes in parallel concurrent lanes for overlapping intervals", async ({ page }) => {
    // 1. Mock a run manifest with two overlapping steps
    const mockManifest = {
      run_id: "run-1",
      workflow: "my-workflow",
      status: "completed",
      started_at: "2026-05-29T15:00:00Z",
      ended_at: "2026-05-29T15:05:00Z",
      steps: [
        {
          id: "step-1",
          status: "completed",
          started_at: "2026-05-29T15:01:00Z",
          ended_at: "2026-05-29T15:02:00Z", // duration: 60s
        },
        {
          id: "step-2",
          status: "completed",
          started_at: "2026-05-29T15:01:30Z", // Overlaps with step-1!
          ended_at: "2026-05-29T15:02:30Z",
        },
      ],
    };

    const mockFiles = {
      "manifest.json": JSON.stringify(mockManifest),
    };

    // Intercept loadRun response
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

    // Navigate to the run details page
    await page.goto("/projects/default/sessions/session-1/workflows/my-workflow/runs/run-1");

    // Verify graphical container is mounted
    const graphContainer = page.locator("[data-testid='workflow-graph-container']");
    await expect(graphContainer).toBeVisible();

    // Verify both step nodes are visible
    const node1 = graphContainer.locator('[aria-label*="step-1"]');
    const node2 = graphContainer.locator('[aria-label*="step-2"]');
    await expect(node1).toBeVisible();
    await expect(node2).toBeVisible();

    // Verify that their vertical bounding box positions differ, representing parallel lane packing
    const box1 = await node1.boundingBox();
    const box2 = await node2.boundingBox();

    expect(box1).not.toBeNull();
    expect(box2).not.toBeNull();
    
    if (box1 && box2) {
      const yDifference = Math.abs(box1.y - box2.y);
      // We expect a significant vertical y difference representing two separate rows/lanes (e.g. ~120px)
      expect(yDifference).toBeGreaterThan(50);
    }
  });
});
