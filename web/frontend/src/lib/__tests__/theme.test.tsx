import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ThemeProvider, useTheme } from "../theme";

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

function mockMatchMedia(matches: Record<string, boolean>): void {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: matches[query] ?? false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

// Test component to consume the hook
const TestComponent = () => {
  const { theme, toggleTheme, setTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <button data-testid="toggle" onClick={toggleTheme}>Toggle</button>
      <button data-testid="set-dark" onClick={() => setTheme("dark")}>Dark</button>
    </div>
  );
};

describe("ThemeProvider & useTheme", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    installStorage();
    mockMatchMedia({ "(prefers-color-scheme: dark)": false });
    delete document.documentElement.dataset.theme;
  });

  it("defaults to light theme if no localstorage", () => {
    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>
    );

    expect(screen.getByTestId("theme").textContent).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("reads initial theme from localStorage", () => {
    localStorage.setItem("armance.theme", "dark");

    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>
    );

    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("toggles theme correctly", async () => {
    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>
    );

    expect(screen.getByTestId("theme").textContent).toBe("light");

    await act(async () => {
      screen.getByTestId("toggle").click();
    });

    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("armance.theme")).toBe("dark");
  });

  it("sets a specific theme", async () => {
    render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>
    );

    await act(async () => {
      screen.getByTestId("set-dark").click();
    });

    expect(screen.getByTestId("theme").textContent).toBe("dark");
  });
});
