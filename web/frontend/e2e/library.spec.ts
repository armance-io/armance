import { test, expect } from "@playwright/test";

test.describe("Library Page E2E", () => {
  test("shows empty library when GET /library returns no documents", async ({ page }) => {
    // Mock the backend call to return an empty library
    await page.route("**/api/projects/*/sessions/*/library", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ docs: [] }),
      });
    });

    await page.goto("/projects/default/sessions/session-1/library");

    // Expect the empty state title and hint scoped under main
    const main = page.locator("main");
    await expect(main.locator("h2")).toContainText("No documents yet");
    await expect(main.locator("p")).toContainText("Import a file to begin.");

    // Expect the importer button to be present
    const importBtn = main.getByRole("button", { name: "Import" }).first();
    await expect(importBtn).toBeVisible();

    // Verify input[type=file] exists
    const fileInput = page.locator("input[type=file]");
    await expect(fileInput).toBeAttached();
    await expect(fileInput).toHaveAttribute("accept", ".pdf,.docx,.md,.txt");
  });

  test("renders rows correctly when GET /library returns documents", async ({ page }) => {
    const mockDocs = [
      { name: "specs.md", format: "md", status: "loaded", size_bytes: 1024 },
      { name: "invoice.pdf", format: "pdf", status: "pending", size_bytes: 204800 },
      { name: "proposal.docx", format: "docx", status: "indexed", size_bytes: 40960 },
    ];

    await page.route("**/api/projects/*/sessions/*/library", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ docs: mockDocs }),
      });
    });

    await page.goto("/projects/default/sessions/session-1/library");

    // Verify list rows are shown
    const listItems = page.locator('[role="listitem"]');
    await expect(listItems).toHaveCount(3);

    // Verify first row
    const firstRow = listItems.nth(0);
    await expect(firstRow).toContainText("specs.md");
    await expect(firstRow).toContainText("md");
    await expect(firstRow).toContainText("loaded");
    await expect(firstRow).toContainText("1 KB");

    // Verify second row
    const secondRow = listItems.nth(1);
    await expect(secondRow).toContainText("invoice.pdf");
    await expect(secondRow).toContainText("pdf");
    await expect(secondRow).toContainText("pending");
    await expect(secondRow).toContainText("200 KB");

    // Verify third row
    const thirdRow = listItems.nth(2);
    await expect(thirdRow).toContainText("proposal.docx");
    await expect(thirdRow).toContainText("docx");
    await expect(thirdRow).toContainText("indexed");
    await expect(thirdRow).toContainText("40 KB");
  });
});
