import { test, expect } from "@playwright/test";

test.describe("LivePanel Deliberation E2E", () => {
  test("loads the generic run page and renders deliverable, arguments, sources, and hypotheses", async ({ page }) => {
    // Navigate to the generic run details page
    await page.goto("/projects/default/sessions/session-1/runs/run-1");

    // Wait for the main page content to be visible
    await expect(page.getByRole("heading", { name: "Steps" })).toBeVisible();

    // 1. Mode Badge Check
    await expect(page.locator("text=autonomous")).toBeVisible();

    // 2. Deliverable Reader Check
    const reader = page.locator("article");
    await expect(reader).toContainText("Synthèse de délibération — VApp Dossier");
    await expect(reader).toContainText("Voici le rapport final de délibération.");

    // 3. Arguments Check (Retained & Rejected)
    // retained column title
    await expect(page.getByRole("heading", { name: "Retained" })).toBeVisible();
    await expect(page.locator("text=Lancer en mode réduit limite le risque marque.")).toBeVisible();

    // rejected column title
    await expect(page.getByRole("heading", { name: "Rejected" })).toBeVisible();
    await expect(page.locator("text=Lancer en mode complet sans étude préalable.")).toBeVisible();
    await expect(page.locator("text=Hypothèse non sourcée ; counter-sample 2024-Q3.")).toBeVisible();

    // 4. Sources Check
    // Locate the Sources collapsible section button and its body
    const sourcesButton = page.getByRole("button", { name: "Sources" });
    await expect(sourcesButton).toBeVisible();
    
    // We expect the source item within the page to be visible
    await expect(page.getByText("Rapport financier 2024 (PDF)").first()).toBeVisible();
    await expect(page.getByText("Article de presse").first()).toBeVisible();

    // 5. Hypotheses Check
    await expect(page.getByText("Hypotheses held by Mona")).toBeVisible();
    await expect(page.getByText("Mona a posé l'hypothèse d'une réduction des coûts.")).toBeVisible();
  });
});
