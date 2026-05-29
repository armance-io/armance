import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nBootstrap } from "../I18nBootstrap";

// Mock i18n
vi.mock("@/lib/i18n", () => ({
  ensureI18n: vi.fn(),
}));

import { ensureI18n } from "@/lib/i18n";

describe("I18nBootstrap", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls ensureI18n on mount and renders children", () => {
    render(
      <I18nBootstrap>
        <span data-testid="child">Hello World</span>
      </I18nBootstrap>
    );

    expect(ensureI18n).toHaveBeenCalled();
    expect(screen.getByTestId("child").textContent).toBe("Hello World");
  });
});
