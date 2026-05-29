import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { AppShell } from "../AppShell";

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
    render(
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
    render(
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
