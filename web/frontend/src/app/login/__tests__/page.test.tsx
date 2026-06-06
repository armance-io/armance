import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock("@/components/visual/Fleuron", () => ({ Fleuron: () => null }));
vi.mock("@/components/visual/ThemeToggle", () => ({ ThemeToggle: () => null }));

const login = vi.fn();
vi.mock("@/lib/api", () => ({ login: (...a: unknown[]) => login(...a) }));

import LoginPage from "../page";

function setLocation(search: string, replace = vi.fn()) {
  Object.defineProperty(window, "location", {
    value: { pathname: "/login", search, replace },
    writable: true,
  });
  return replace;
}

describe("LoginPage", () => {
  beforeEach(() => {
    login.mockReset();
  });

  it("renders the login form when there is no ?token", () => {
    setLocation("");
    render(<LoginPage />);
    expect(screen.getByTestId("login-page")).toBeTruthy();
    expect(screen.getByTestId("login-input")).toBeTruthy();
  });

  it("submits the token and redirects to next on success", async () => {
    const replace = setLocation("?next=%2Fprojects%2Fdefault");
    login.mockResolvedValue(true);
    render(<LoginPage />);

    fireEvent.change(screen.getByTestId("login-input"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByTestId("login-submit"));

    await waitFor(() => expect(login).toHaveBeenCalledWith("secret"));
    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/projects/default"),
    );
  });

  it("shows an error on an invalid token", async () => {
    setLocation("");
    login.mockResolvedValue(false);
    render(<LoginPage />);

    fireEvent.change(screen.getByTestId("login-input"), {
      target: { value: "bad" },
    });
    fireEvent.click(screen.getByTestId("login-submit"));

    await waitFor(() => expect(screen.getByTestId("login-error")).toBeTruthy());
  });

  it("rejects an off-site next (open-redirect guard)", async () => {
    const replace = setLocation("?next=https%3A%2F%2Fevil.com");
    login.mockResolvedValue(true);
    render(<LoginPage />);

    fireEvent.change(screen.getByTestId("login-input"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByTestId("login-submit"));

    await waitFor(() => expect(replace).toHaveBeenCalled());
    expect(replace).toHaveBeenCalledWith("/"); // not evil.com
  });

  it("rejects a scheme-relative //host next", async () => {
    const replace = setLocation("?token=t&next=%2F%2Fevil.com");
    login.mockResolvedValue(true);
    render(<LoginPage />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  });

  it("SEC5 — auto-logs-in from ?token and strips it", async () => {
    const replace = setLocation("?token=urltok&next=%2F");
    login.mockResolvedValue(true);
    render(<LoginPage />);

    await waitFor(() => expect(login).toHaveBeenCalledWith("urltok"));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  });
});
