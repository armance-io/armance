import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { AppShell } from "../AppShell";

// SidebarNav reads the route via next/navigation; HeaderMetrics + SidebarNav
// query the API. Provide a pathname + a QueryClient so AppShell renders.
vi.mock("next/navigation", () => ({ usePathname: () => "/projects/default/sessions/s1" }));

function renderShell(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function installStorage(): void {
  const store: Record<string, string> = {};
  const fake: Storage = {
    get length(): number {
      return Object.keys(store).length;
    },
    clear(): void {
      for (const k of Object.keys(store)) delete store[k];
    },
    getItem(key: string): string | null {
      return store[key] ?? null;
    },
    key(index: number): string | null {
      return Object.keys(store)[index] ?? null;
    },
    removeItem(key: string): void {
      delete store[key];
    },
    setItem(key: string, value: string): void {
      store[key] = String(value);
    },
  };
  Object.defineProperty(window, "localStorage", {
    value: fake,
    writable: true,
    configurable: true,
  });
}

function mockMatchMedia(): void {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

describe("AppShell", () => {
  beforeEach(() => {
    installStorage();
    mockMatchMedia();
  });

  const mockT = (key: string) => key;

  it("renders brand, sidebar, children, and footer", () => {
    renderShell(
      <AppShell
        sidebar={<div data-testid="sidebar">Sidebar Content</div>}
        t={mockT}
      >
        <div data-testid="children">Main Content</div>
      </AppShell>
    );

    expect(screen.getByTestId("sidebar")).toBeDefined();
    expect(screen.getByTestId("children")).toBeDefined();
    expect(screen.getByText("Armance")).toBeDefined();
    expect(screen.getByText("visual:shell.brand_domain")).toBeDefined();
    expect(screen.getByText("visual:shell.footer_motto")).toBeDefined();
    expect(screen.getByText("visual:shell.footer_line")).toBeDefined();
  });

  it("collapses and expands sidebar on button click", async () => {
    renderShell(
      <AppShell
        sidebar={<div data-testid="sidebar">Sidebar Content</div>}
        t={mockT}
      >
        <div data-testid="children">Main Content</div>
      </AppShell>
    );

    const button = screen.getByRole("button", { name: "visual:shell.sidebar_collapse_aria" });
    expect(button.getAttribute("aria-expanded")).toBe("true");

    await act(async () => {
      button.click();
    });

    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(localStorage.getItem("armance.sidebar-collapsed")).toBe("true");
  });
});
