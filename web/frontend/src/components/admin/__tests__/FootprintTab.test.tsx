import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FootprintTab } from "../FootprintTab";
import type { FootprintResponse } from "../../../lib/footprint";

const mockT = (key: string) => key;

describe("<FootprintTab />", () => {
  const mockData: FootprintResponse = {
    by_agent: {
      Armance: {
        gco2e: 24.5,
        water_ml: 120,
        calls: 2,
        has_estimate: true,
        has_unknown: false,
      },
    },
    by_day: {},
    by_month: {},
    by_session: {},
    dominant_zone: "WOR",
  };

  it("renders correctly with loaded agent rollup metrics", () => {
    render(
      <FootprintTab
        data={mockData}
        loading={false}
        error={null}
        zone="WOR"
        t={mockT}
      />
    );

    expect(screen.getByText("Armance")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined();
    expect(screen.getByText("~24.5 gCO₂e")).toBeDefined();
    expect(screen.getByText("120 mL")).toBeDefined();
    expect(screen.getByText("Estimation")).toBeDefined();
  });

  it("toggles the Méthode provenance expander panel on click", () => {
    render(
      <FootprintTab
        data={mockData}
        loading={false}
        error={null}
        zone="FRA"
        t={mockT}
      />
    );

    // Expander should be closed initially
    expect(screen.queryByTestId("methode-panel")).toBeNull();

    // Click expander button
    const btn = screen.getByRole("button", { name: /méthode/i });
    fireEvent.click(btn);

    // Expander should be open and contain critical methodology citations
    const panel = screen.getByTestId("methode-panel");
    expect(panel).toBeDefined();
    expect(panel.textContent).toContain("EcoLogits");
    expect(panel.textContent).toContain("ISO 14044");
    expect(panel.textContent).toContain("FRA");

    // Click again to close
    fireEvent.click(btn);
    expect(screen.queryByTestId("methode-panel")).toBeNull();
  });
});
