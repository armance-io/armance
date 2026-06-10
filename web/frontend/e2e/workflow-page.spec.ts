import { test, expect } from "./fixtures";

test.describe("Workflow Assembly & Transition E2E (D-WIRE.8)", () => {
  test("transitions from idle depth-picker launcher to live panel upon successful launch", async ({ page }) => {
    let activeWorkflowState: any = null;
    let runsListState: any[] = [];

    // 1. Mock active workflow state
    await page.route(
      "**/api/projects/*/sessions/*/active-workflow",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ active: activeWorkflowState }),
        });
      }
    );

    // Mock runs list history endpoint
    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(runsListState),
        });
      }
    );

    // Mock workflow config fallback endpoint
    await page.route(
      "**/api/projects/*/sessions/*/workflows/my-workflow",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            nodes: [
              {
                id: "step-1",
                data: {
                  step_id: "step-1",
                  role: "recruiter",
                  status: "queued",
                },
              },
            ],
            edges: [],
          }),
        });
      }
    );

    // Mock launch endpoint (matches the real endpoint POST .../run)
    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/run",
      async (route) => {
        expect(route.request().method()).toBe("POST");
        const body = route.request().postDataJSON();
        expect(body.mode).toBe("autonomous");
        expect(body.depth).toBe("deep");

        // Transition states dynamically on launch
        activeWorkflowState = {
          workflow: "my-workflow",
          run_id: "run-1",
          manifest_path: "manifest.json",
        };
        runsListState = [
          {
            run_id: "run-1",
            status: "running",
            started_at: new Date().toISOString(),
            ended_at: null,
            duration_ms: 0,
            tokens_total: 0,
          },
        ];

        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ run_id: "run-1" }),
        });
      }
    );

    // Mock run manifest endpoint for live polling
    const mockManifest = {
      run_id: "run-1",
      workflow: "my-workflow",
      status: "running",
      mode: "autonomous",
      started_at: "2026-05-29T15:00:00Z",
      ended_at: null,
      steps: [
        {
          id: "step-1",
          status: "working",
        },
      ],
    };

    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs/run-1",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            "manifest.json": JSON.stringify(mockManifest),
            "deliverable.md": "# Deliberation synthetic results\n\nActive processing content here.",
          }),
        });
      }
    );

    // Mock run details endpoints for parallel query loading
    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs/run-1/arguments",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ arguments: [] }),
        });
      }
    );

    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs/run-1/sources",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ sources: [] }),
        });
      }
    );

    await page.route(
      "**/api/projects/*/sessions/*/workflows/*/runs/run-1/hypotheses",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ hypotheses: [] }),
        });
      }
    );

    // Mock workflows list so the DepthPicker renders (workflow exists)
    await page.route(
      "**/api/projects/*/sessions/*/workflows",
      async (route) => {
        if (route.request().method() === "GET" && !route.request().url().match(/\/workflows\/[^/]+\//)) {
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

    // 2. Navigate to workflow launcher screen
    await page.goto("/projects/default/sessions/session-1/workflows/my-workflow");

    // 3. Verify page is initially idle and DepthPicker is visible in the right panel
    // Graph heading is first, DepthPicker heading is second.
    const depthPickerTitle = page.getByRole("heading", { name: "my-workflow" }).nth(1);
    await expect(depthPickerTitle).toBeVisible();

    const quickCard = page.getByRole("radio", { name: "A quick perspective" });
    const deepCard = page.getByRole("radio", { name: "A thorough, challenged analysis" });
    await expect(quickCard).toBeVisible();
    await expect(deepCard).toBeVisible();

    const modeInteractiveBtn = page.getByRole("radio", { name: "interactive" });
    const modeAutonomousBtn = page.getByRole("radio", { name: "autonomous" });
    await expect(modeInteractiveBtn).toBeVisible();
    await expect(modeAutonomousBtn).toBeVisible();

    // LivePanel should be hidden initially
    const livePanelTabs = page.getByRole("button", { name: "Arguments" });
    await expect(livePanelTabs).not.toBeVisible();

    // 4. Select depth & mode configuration on DepthPicker and launch
    await deepCard.click();
    await modeAutonomousBtn.click();

    const launchBtn = page.getByRole("button", { name: "Launch" });
    await expect(launchBtn).toBeVisible();
    await launchBtn.click();

    // 5. Assert seamless dynamic transition to live deliberation panel
    // Switch to the Report tab to display the LivePanel content
    await page.getByRole("tab", { name: /report|compte rendu/i }).click();

    // Wait for LivePanel component contents to render and become visible
    const deliverableTab = page.getByRole("button", { name: /deliverable/i });
    await expect(deliverableTab).toBeVisible();

    // Assert that the manifest synthesis content loads successfully
    await expect(page.locator("text=Active processing content here.")).toBeVisible();

    // 6. Assert run history in the sidebar contains the new active run
    const sidebar = page.locator("aside");
    const historySection = sidebar.locator("#run-history-list");
    await expect(historySection).toBeVisible();

    const newActiveRow = historySection.locator('.run-row[aria-label*="run-1"]');
    await expect(newActiveRow).toBeVisible();
    await expect(newActiveRow).toContainText("⏳");
  });
});
