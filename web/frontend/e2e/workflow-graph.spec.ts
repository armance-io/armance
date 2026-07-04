import { test, expect } from "./fixtures";

test.describe("Workflow Graph Live E2E", () => {
  test("renders the real DAG with live statuses and visible edges", async ({ page }) => {
    // Real workflow detail (the graph no longer falls back to a fixture).
    const mockWorkflow = {
      name: "my-workflow",
      scope: "x",
      strategy: "",
      steps: [
        { id: "step-1", kind: "task", role: "pilote", depends_on: [] },
        { id: "step-2", kind: "task", role: "securite", depends_on: [] },
        { id: "step-3", kind: "judge", role: "mona", depends_on: ["step-1", "step-2"] },
      ],
      graph: {
        nodes: [
          { id: "step-1", position: { x: 0, y: 0 }, data: { step_id: "step-1", kind: "task", role: "pilote" } },
          { id: "step-2", position: { x: 0, y: 120 }, data: { step_id: "step-2", kind: "task", role: "securite" } },
          { id: "step-3", position: { x: 240, y: 60 }, data: { step_id: "step-3", kind: "judge", role: "mona" } },
        ],
        edges: [
          { id: "step-1->step-3", source: "step-1", target: "step-3" },
          { id: "step-2->step-3", source: "step-2", target: "step-3" },
        ],
      },
    };

    const mockManifest = {
      run_id: "run-1",
      workflow: "my-workflow",
      status: "working",
      started_at: "2026-05-29T15:00:00Z",
      ended_at: null,
      steps: [
        {
          id: "step-1",
          status: "completed",
          agent: "Elise",
          started_at: "2026-05-29T15:01:00Z",
          ended_at: "2026-05-29T15:02:00Z",
          duration_ms: 60000,
        },
        {
          id: "step-2",
          status: "working",
          started_at: "2026-05-29T15:01:30Z",
        },
      ],
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
    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs/run-1",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ "manifest.json": JSON.stringify(mockManifest) }),
        });
      }
    );

    await page.goto("/projects/default/sessions/session-1/workflows/my-workflow/runs/run-1");

    const graphContainer = page.locator("[data-testid='workflow-graph-container']");
    await expect(graphContainer).toBeVisible();

    // All three real steps render.
    const node1 = graphContainer.locator('[data-id="step-1"]');
    const node2 = graphContainer.locator('[data-id="step-2"]');
    const node3 = graphContainer.locator('[data-id="step-3"]');
    await expect(node1).toBeVisible();
    await expect(node2).toBeVisible();
    await expect(node3).toBeVisible();

    // Live statuses merged from the manifest (the inner StepNode div's
    // aria-label carries the status), and completed steps name who spoke.
    await expect(node1.locator('[aria-label*="completed"]')).toBeVisible();
    await expect(node1).toContainText("Elise");
    await expect(node2.locator('[aria-label*="working"]')).toBeVisible();
    await expect(node3.locator('[aria-label*="queued"]')).toBeVisible();

    // Regression W10: custom nodes without real React Flow <Handle>
    // components render NO edges at all — the DAG showed floating boxes.
    const edges = graphContainer.locator(".react-flow__edge");
    await expect(edges).toHaveCount(2);

    // Same-rank parallel steps are vertically separated (dagre nodesep).
    const box1 = await node1.boundingBox();
    const box2 = await node2.boundingBox();
    expect(box1).not.toBeNull();
    expect(box2).not.toBeNull();
    if (box1 && box2) {
      expect(Math.abs(box1.y - box2.y)).toBeGreaterThan(50);
    }
  });
});
