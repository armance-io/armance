import { describe, it, expect } from "vitest";
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
    // Type badge label is i18n-driven (identity t → key).
    expect(screen.getByText("admin:footprint.estimate")).toBeDefined();
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

    // Click expander button (label is i18n-driven → the key under identity t)
    const btn = screen.getByRole("button", { name: /admin:footprint\.method/i });
    fireEvent.click(btn);

    // Expander open: method body key rendered + the configured zone shown
    const panel = screen.getByTestId("methode-panel");
    expect(panel).toBeDefined();
    expect(panel.textContent).toContain("admin:footprint.method_body");
    expect(panel.textContent).toContain("FRA");

    // Click again to close
    fireEvent.click(btn);
    expect(screen.queryByTestId("methode-panel")).toBeNull();
  });
});
