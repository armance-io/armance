import { test, expect } from "./fixtures";

test.describe("Workflow Graph Preview E2E", () => {
  test("renders the designed DAG nodes and their connections LR", async ({ page }) => {
    // The graph renders the REAL workflow (no placeholder fixture): the
    // preview of a designed-but-not-run workflow shows its actual steps.
    const mockWorkflow = {
      name: "my-workflow",
      scope: "x",
      strategy: "",
      steps: [
        { id: "step-1", kind: "task", role: "recruiter", depends_on: [] },
        { id: "step-2", kind: "judge", role: "judge", depends_on: ["step-1"] },
        { id: "step-3", kind: "task", role: "specialist", depends_on: ["step-2"] },
      ],
      graph: {
        nodes: [
          { id: "step-1", position: { x: 0, y: 0 }, data: { step_id: "step-1", kind: "task", role: "recruiter" } },
          { id: "step-2", position: { x: 240, y: 0 }, data: { step_id: "step-2", kind: "judge", role: "judge" } },
          { id: "step-3", position: { x: 480, y: 0 }, data: { step_id: "step-3", kind: "task", role: "specialist" } },
        ],
        edges: [
          { id: "step-1->step-2", source: "step-1", target: "step-2" },
          { id: "step-2->step-3", source: "step-2", target: "step-3" },
        ],
      },
    };

    await page.route(
      "**/api/projects/*/sessions/*/workflows/my-workflow",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockWorkflow),
        });
      }
    );

    await page.goto("/projects/default/sessions/session-1/workflows/my-workflow/preview");

    const main = page.locator("main");
    const graphWrapper = main.locator('[data-testid="workflow-graph-container"]');
    await expect(graphWrapper).toBeVisible();

    const node1 = graphWrapper.locator('[data-id="step-1"]');
    const node2 = graphWrapper.locator('[data-id="step-2"]');
    const node3 = graphWrapper.locator('[data-id="step-3"]');

    await expect(node1).toBeVisible();
    await expect(node2).toBeVisible();
    await expect(node3).toBeVisible();

    await expect(node1).toContainText("step-1");
    await expect(node1).toContainText("recruiter");
    await expect(node2).toContainText("judge");
    await expect(node3).toContainText("specialist");

    // Chain edges are drawn (W10: no real <Handle> → no edges at all).
    await expect(graphWrapper.locator(".react-flow__edge")).toHaveCount(2);

    // Left-to-right layout: step-1 x < step-2 x < step-3 x.
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
