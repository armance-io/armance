import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
vi.mock("@/components/visual/Fleuron", () => ({ Fleuron: () => null }));
vi.mock("@/components/visual/ThemeToggle", () => ({ ThemeToggle: () => null }));
vi.mock("@/components/launcher/FolderExplorer", () => ({
  FolderExplorer: ({ onSelect }: { onSelect: (p: string) => void }) => (
    <div data-testid="folder-explorer">
      <button data-testid="explorer-select" onClick={() => onSelect("/picked/folder")}>
        use
      </button>
    </div>
  ),
}));

const getLauncher = vi.fn();
const openProject = vi.fn();
const newProject = vi.fn();
vi.mock("@/lib/api", () => ({
  getLauncher: (...a: unknown[]) => getLauncher(...a),
  openProject: (...a: unknown[]) => openProject(...a),
  newProject: (...a: unknown[]) => newProject(...a),
}));

import LauncherPage from "../page";

function setAssign() {
  const assign = vi.fn();
  Object.defineProperty(window, "location", {
    value: { assign, pathname: "/launcher" },
    writable: true,
  });
  return assign;
}

const PROJECT = {
  id: "alpha-1234abcd",
  name: "alpha",
  path: "/home/u/alpha",
  last_opened: "2026-06-07T00:00:00Z",
  exists: true,
};

describe("LauncherPage", () => {
  beforeEach(() => {
    getLauncher.mockReset();
    openProject.mockReset();
    newProject.mockReset();
  });

  it("lists projects from the registry", async () => {
    getLauncher.mockResolvedValue({ projects: [PROJECT] });
    render(<LauncherPage />);
    await waitFor(() => expect(screen.getByTestId("launcher-list")).toBeInTheDocument());
    expect(screen.getByTestId("project-card")).toHaveAttribute("data-pid", "alpha-1234abcd");
  });

  it("shows the empty state when there are no projects", async () => {
    getLauncher.mockResolvedValue({ projects: [] });
    render(<LauncherPage />);
    await waitFor(() => expect(screen.getByTestId("launcher-empty")).toBeInTheDocument());
  });

  it("opens a project and navigates to /projects/{pid}", async () => {
    const assign = setAssign();
    getLauncher.mockResolvedValue({ projects: [PROJECT] });
    openProject.mockResolvedValue({ id: "alpha-1234abcd", name: "alpha", path: "/home/u/alpha" });
    render(<LauncherPage />);
    await waitFor(() => screen.getByTestId("project-open"));
    fireEvent.click(screen.getByTestId("project-open"));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("/projects/alpha-1234abcd"));
  });

  it("creates a project via the folder picker and navigates", async () => {
    const assign = setAssign();
    getLauncher.mockResolvedValue({ projects: [] });
    newProject.mockResolvedValue({ id: "folder-deadbeef", name: "folder", path: "/picked/folder" });
    render(<LauncherPage />);
    await waitFor(() => screen.getByTestId("launcher-new"));
    fireEvent.click(screen.getByTestId("launcher-new"));
    fireEvent.click(screen.getByTestId("explorer-select"));
    await waitFor(() => expect(newProject).toHaveBeenCalledWith("/picked/folder"));
    expect(assign).toHaveBeenCalledWith("/projects/folder-deadbeef");
  });

  it("surfaces an error when open fails", async () => {
    setAssign();
    getLauncher.mockResolvedValue({ projects: [PROJECT] });
    openProject.mockImplementation(async () => {
      throw new Error("boom");
    });
    render(<LauncherPage />);
    await waitFor(() => screen.getByTestId("project-open"));
    fireEvent.click(screen.getByTestId("project-open"));
    await waitFor(() => expect(screen.getByTestId("launcher-error")).toBeInTheDocument());
  });
});
