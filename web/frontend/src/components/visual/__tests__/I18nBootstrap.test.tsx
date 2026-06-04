import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nBootstrap } from "../I18nBootstrap";

// Mock i18n
vi.mock("@/lib/i18n", () => ({
  ensureI18n: vi.fn(() => ({
    language: "en",
    changeLanguage: vi.fn(),
  })),
}));

// Mock api
vi.mock("@/lib/api", () => ({
  getAdminConfig: vi.fn(() => Promise.resolve({ language: "fr" })),
}));

import { ensureI18n } from "@/lib/i18n";

describe("I18nBootstrap", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls ensureI18n on mount and renders children", async () => {
    render(
      <I18nBootstrap>
        <span data-testid="child">Hello World</span>
      </I18nBootstrap>
    );

    expect(ensureI18n).toHaveBeenCalled();
    const child = await screen.findByTestId("child");
    expect(child.textContent).toBe("Hello World");
  });
});
