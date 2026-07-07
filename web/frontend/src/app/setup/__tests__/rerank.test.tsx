import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock("@/components/visual/Fleuron", () => ({ Fleuron: () => null }));
vi.mock("@/components/visual/ThemeToggle", () => ({ ThemeToggle: () => null }));
vi.mock("@/components/visual/LanguageFlag", () => ({ LanguageFlag: () => null }));

vi.mock("@/lib/api", () => ({
  initSetup: vi.fn(),
  getProviders: vi.fn().mockResolvedValue([]),
  getEmbeddingModels: vi.fn().mockResolvedValue([]),
  getFootprintZones: vi.fn().mockResolvedValue([]),
}));

import SetupPage from "../page";

async function advanceToEmbeddingStep({ withOpenRouter = false } = {}) {
  render(<SetupPage />);
  // Step 1 → 2 → 3 via the Next button (label is the i18n key, identity-mocked).
  const next = () => screen.getByText("common:next");
  fireEvent.click(next()); // step 1 → 2
  if (withOpenRouter) {
    // Add a rerank-capable provider next to the default gemini selection.
    fireEvent.click(screen.getByText("OpenRouter"));
    const orKey = await screen.findByPlaceholderText("sk-or-...");
    fireEvent.change(orKey, { target: { value: "k" } });
  }
  // Default selectedProviders = ["gemini"]; fill its API key so step-2 validates.
  const keyInput = await screen.findByPlaceholderText("AIzaSy...");
  fireEvent.change(keyInput, { target: { value: "k" } });
  fireEvent.click(next()); // step 2 → 3
}

describe("SetupPage rerank field", () => {
  it("hides the rerank input until an embedding model is set", async () => {
    await advanceToEmbeddingStep({ withOpenRouter: true });
    // Embedding block is visible (gemini is an embedding provider) but rerank
    // input only appears once an embedding model is typed.
    expect(screen.queryByTestId("setup-rerank-model")).toBeNull();
  });

  it("shows the rerank input below embedding once an embedding model is set", async () => {
    await advanceToEmbeddingStep({ withOpenRouter: true });
    const embeddingInput = screen.getByPlaceholderText("setup:embedding_placeholder");
    fireEvent.change(embeddingInput, { target: { value: "text-embedding-3-small" } });
    await waitFor(() =>
      expect(screen.getByTestId("setup-rerank-model")).toBeTruthy(),
    );
  });

  it("offers a rerank provider decoupled from the embedding provider", async () => {
    await advanceToEmbeddingStep({ withOpenRouter: true });
    const embeddingInput = screen.getByPlaceholderText("setup:embedding_placeholder");
    fireEvent.change(embeddingInput, { target: { value: "text-embedding-3-small" } });
    const providerSelect = (await screen.findByTestId(
      "setup-rerank-provider",
    )) as HTMLSelectElement;
    // gemini serves the embedding but has no /rerank endpoint — it must not
    // be offered; openrouter is the only eligible selected provider here.
    const values = Array.from(providerSelect.options).map((o) => o.value);
    expect(values).toEqual(["openrouter"]);
    expect(providerSelect.value).toBe("openrouter");
  });

  it("hides rerank entirely when no selected provider supports it", async () => {
    // gemini-only selection: embedding works but rerank has no eligible
    // provider → the whole rerank block stays hidden.
    await advanceToEmbeddingStep();
    const embeddingInput = screen.getByPlaceholderText("setup:embedding_placeholder");
    fireEvent.change(embeddingInput, { target: { value: "text-embedding-3-small" } });
    expect(screen.queryByTestId("setup-rerank-model")).toBeNull();
    expect(screen.queryByTestId("setup-rerank-provider")).toBeNull();
  });
});
