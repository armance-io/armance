import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatsDashboard, type AgentStat } from "../StatsDashboard";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));

const t = (k: string) => k;

const agent = (over: Partial<AgentStat>): AgentStat => ({
  agent: "Etienne",
  tokens_in: 10,
  tokens_out: 100,
  cost: 0,
  messages: 2,
  ...over,
});

describe("StatsDashboard — carbon range", () => {
  it("renders a [min – max] range when bounds differ", () => {
    const agents = [
      agent({ gco2e: 0.06, gco2e_min: 0.034, gco2e_max: 0.086, has_estimate: false }),
    ];
    render(<StatsDashboard agents={agents} t={t} />);
    // total card shows the summed range
    expect(screen.getAllByText(/\[0\.0\s+–\s+0\.1\]\s*gCO₂e/).length).toBeGreaterThan(0);
  });

  it("renders a flat value when min == max", () => {
    const agents = [
      agent({ gco2e: 0.06, gco2e_min: 0.06, gco2e_max: 0.06, has_estimate: false }),
    ];
    render(<StatsDashboard agents={agents} t={t} />);
    expect(screen.getAllByText(/^0\.1 gCO₂e$/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/\[/)).toBeNull();
  });
});

describe("StatsDashboard — ADEME equivalences", () => {
  it("renders human-scale equivalences when provided", () => {
    const agents = [agent({ gco2e: 8.3, water_ml: 250 })];
    render(
      <StatsDashboard
        agents={agents}
        t={t}
        equiv={{ phone_charges: 1, car_km: 0.04, water_glasses: 1 }}
      />,
    );
    expect(screen.getByTestId("footprint-equiv")).toBeTruthy();
  });

  it("omits the equivalences block when none provided", () => {
    render(<StatsDashboard agents={[agent({ gco2e: 0.06 })]} t={t} />);
    expect(screen.queryByTestId("footprint-equiv")).toBeNull();
  });
});
