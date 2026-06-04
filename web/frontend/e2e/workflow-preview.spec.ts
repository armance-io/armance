import { test, expect } from "@playwright/test";

test.describe("Workflow Graph Preview E2E", () => {
  test("renders 3 topological nodes and their connections LR", async ({ page }) => {
    // Navigate to the preview page
    await page.goto("/projects/default/sessions/session-1/workflows/my-workflow/preview");

    const main = page.locator("main");

    // Verify WorkflowGraphContainer wrapper is present
    const graphWrapper = main.locator('[data-testid="workflow-graph-container"]');
    await expect(graphWrapper).toBeVisible();

    // Verify all 3 step nodes exist and show their respective step IDs
    const node1 = graphWrapper.locator('[data-id="step-1"]');
    const node2 = graphWrapper.locator('[data-id="step-2"]');
    const node3 = graphWrapper.locator('[data-id="step-3"]');

    await expect(node1).toBeVisible();
    await expect(node2).toBeVisible();
    await expect(node3).toBeVisible();

    // Verify step nodes display correct step ID text
    await expect(node1).toContainText("step-1");
    await expect(node2).toContainText("step-2");
    await expect(node3).toContainText("step-3");

    // Verify roles and status indicators are rendered
    await expect(node1).toContainText("recruiter");
    await expect(node1).toContainText("1.5s");

    await expect(node2).toContainText("judge");

    await expect(node3).toContainText("specialist");

    // Verify Left-to-Right layout structure (step-1 x < step-2 x < step-3 x)
    const box1 = await node1.boundingBox();
    const box2 = await node2.boundingBox();
    const box3 = await node3.boundingBox();

    expect(box1).not.toBeNull();
    expect(box2).not.toBeNull();
    expect(box3).not.toBeNull();

    if (box1 && box2 && box3) {
      expect(box1.x).toBeLessThan(box2.x);
      expect(box2.x).toBeLessThan(box3.x);
    }
  });
});
