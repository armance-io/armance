import { test, expect } from "./fixtures";

test.describe("Landing page / AppShell e2e", () => {
  test("loads the landing page and shows AppShell elements", async ({ page }) => {
    await page.goto("/");

    // Header shows "Armance" and "armance.io"
    await expect(page.locator("header")).toContainText("Armance");
    await expect(page.locator("header")).toContainText("armance.io");

    // Footer shows fleuron (❦) and motto
    await expect(page.locator("footer")).toContainText("❦");
    await expect(page.locator("footer")).toContainText("A house of agents to sharpen your thinking.");
    await expect(page.locator("footer")).toContainText("armance.io · 2026 · made in France");

    // Main content area renders EmptySession
    const main = page.locator("main");
    await expect(main.locator("h2")).toContainText("A new session begins");
    await expect(main.locator("p")).toContainText("Describe a decision you're weighing, or drop a document.");

    // ThemeToggle is present and keyboard-accessible (can be focused and toggled)
    const toggle = page.locator(".theme-toggle");
    await expect(toggle).toBeVisible();
    await toggle.focus();
    await expect(toggle).toBeFocused();

    // Toggle works
    const html = page.locator("html");
    const initialTheme = await html.getAttribute("data-theme") || "light";

    // Pressing Space or Enter triggers the toggle
    await page.keyboard.press("Space");
    
    // Wait for the toggle transition (around 200ms)
    await page.waitForTimeout(250);
    
    const toggledTheme = await html.getAttribute("data-theme");
    expect(toggledTheme).not.toBe(initialTheme);
  });
});
