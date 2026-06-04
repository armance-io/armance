import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { HeaderModel } from "../HeaderModel";

// Mock routeParams
vi.mock("@/lib/routeParams", () => ({
  useRouteParams: () => ({ pid: "p1", sid: "s1" }),
}));

// Mock agentBus
const mockCurrentAgent = vi.fn();
vi.mock("@/lib/agentBus", () => ({
  useCurrentAgent: () => mockCurrentAgent(),
}));

// Mock api
const mockGetAdminAgents = vi.fn();
vi.mock("@/lib/api", () => ({
  getAdminAgents: (pid: string, sid: string) => mockGetAdminAgents(pid, sid),
}));

function renderHeader(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("<HeaderModel />", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    document.body.innerHTML = "";
  });

  const stubT = (k: string) => k;

  it("renders null when no model is available", async () => {
    mockCurrentAgent.mockReturnValue("Sara");
    mockGetAdminAgents.mockResolvedValue([]);

    const { container } = renderHeader(<HeaderModel t={stubT} />);
    // Wait for the query to resolve
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(container.firstChild).toBeNull();
  });

  it("renders base model when agent is not boosted", async () => {
    mockCurrentAgent.mockReturnValue("Sara");
    mockGetAdminAgents.mockResolvedValue([
      {
        name: "Sara",
        slug: "Sara",
        domain: "helper",
        role: "helper",
        provider: "openrouter",
        model: "anthropic/claude-3.5-sonnet",
        reasoning: null,
        staff: false,
        boosted: false,
        effective_model: "anthropic/claude-3.5-sonnet",
      },
    ]);

    const headerEl = document.createElement("header");
    document.body.appendChild(headerEl);

    renderHeader(<HeaderModel t={stubT} />);

    expect(await screen.findByText("anthropic/claude-3.5-sonnet")).toBeDefined();
    expect(headerEl.classList.contains("ae-header-boost-glow")).toBe(false);
  });

  it("renders effective model and triggers glow class when agent is boosted", async () => {
    mockCurrentAgent.mockReturnValue("Sara");
    mockGetAdminAgents.mockResolvedValue([
      {
        name: "Sara",
        slug: "Sara",
        domain: "helper",
        role: "helper",
        provider: "openrouter",
        model: "anthropic/claude-3.5-sonnet",
        reasoning: null,
        staff: false,
        boosted: true,
        effective_model: "anthropic/claude-opus-4-5",
      },
    ]);

    const headerEl = document.createElement("header");
    document.body.appendChild(headerEl);

    renderHeader(<HeaderModel t={stubT} />);

    expect(await screen.findByText("anthropic/claude-opus-4-5")).toBeDefined();
    expect(headerEl.classList.contains("ae-header-boost-glow")).toBe(true);
  });
});
