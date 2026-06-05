/**
 * D3 — FootprintChip renders a range when carbon bounds differ,
 * an estimate badge when has_estimate, and a single value otherwise.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { FootprintChip } from "../FootprintChip";

// Return the key so assertions stay language-agnostic.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe("FootprintChip", () => {
  it("renders a single value when no bounds are given", () => {
    render(<FootprintChip gco2e={0.4} water_ml={null} hasEstimate={false} showWater={false} />);
    const chip = screen.getByTestId("footprint-chip");
    expect(chip.textContent).toContain("0.4gCO₂e");
    expect(chip.textContent).not.toContain("–");
  });

  it("renders a range string when min/max differ", () => {
    render(
      <FootprintChip
        gco2e={0.4}
        gco2eMin={0.2}
        gco2eMax={0.6}
        water_ml={null}
        hasEstimate
        showWater={false}
      />,
    );
    const chip = screen.getByTestId("footprint-chip");
    expect(chip.textContent).toContain("[0.2 – 0.6]gCO₂e");
  });

  it("collapses to a single value when min equals max", () => {
    render(
      <FootprintChip
        gco2e={0.4}
        gco2eMin={0.4}
        gco2eMax={0.4}
        water_ml={null}
        hasEstimate={false}
        showWater={false}
      />,
    );
    const chip = screen.getByTestId("footprint-chip");
    expect(chip.textContent).toContain("0.4gCO₂e");
    expect(chip.textContent).not.toContain("–");
  });

  it("shows an estimate badge when hasEstimate is true", () => {
    render(<FootprintChip gco2e={0.4} water_ml={null} hasEstimate showWater={false} />);
    expect(screen.getByTestId("footprint-estimate-badge")).toBeTruthy();
    expect(screen.getByTestId("footprint-estimate-badge").textContent).toBe(
      "admin:footprint.estimate_badge",
    );
  });

  it("hides the estimate badge when hasEstimate is false", () => {
    render(<FootprintChip gco2e={0.4} water_ml={null} hasEstimate={false} showWater={false} />);
    expect(screen.queryByTestId("footprint-estimate-badge")).toBeNull();
  });

  it("renders the unknown chip when gco2e is null", () => {
    render(<FootprintChip gco2e={null} water_ml={null} hasEstimate={false} showWater={false} />);
    expect(screen.getByTestId("footprint-chip").textContent).toContain("🌱?");
  });
});
