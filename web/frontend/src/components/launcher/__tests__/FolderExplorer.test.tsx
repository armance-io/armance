import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock("@/lib/api", () => ({
  browseFolders: vi.fn(),
  makeFolder: vi.fn(),
}));

import * as api from "@/lib/api";
import { FolderExplorer } from "../FolderExplorer";

const browseFolders = vi.mocked(api.browseFolders);
const makeFolder = vi.mocked(api.makeFolder);

const HOME = {
  path: "/home/u",
  root: "/home/u",
  parent: null,
  dirs: [{ name: "projects", path: "/home/u/projects" }],
};

describe("FolderExplorer", () => {
  beforeEach(() => {
    browseFolders.mockReset();
    makeFolder.mockReset();
  });

  it("lists subdirs of the starting folder", async () => {
    browseFolders.mockResolvedValue(HOME);
    render(<FolderExplorer onSelect={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("explorer-dir")).toHaveTextContent("projects"));
    expect(screen.getByTestId("explorer-path")).toHaveTextContent("/home/u");
  });

  it("descends into a clicked subdir", async () => {
    browseFolders.mockResolvedValueOnce(HOME).mockResolvedValueOnce({
      path: "/home/u/projects",
      root: "/home/u",
      parent: "/home/u",
      dirs: [],
    });
    render(<FolderExplorer onSelect={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("explorer-dir"));
    fireEvent.click(screen.getByTestId("explorer-dir"));
    await waitFor(() => expect(browseFolders).toHaveBeenCalledWith("/home/u/projects"));
  });

  it("returns the current path on select", async () => {
    const onSelect = vi.fn();
    browseFolders.mockResolvedValue(HOME);
    render(<FolderExplorer onSelect={onSelect} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("explorer-select"));
    fireEvent.click(screen.getByTestId("explorer-select"));
    expect(onSelect).toHaveBeenCalledWith("/home/u");
  });

  it("shows an error when a descend fails", async () => {
    // First load (effect) succeeds; the failing browse is triggered from a
    // click handler — the rejection is consumed inside an event, not a
    // fire-and-forget effect, so it renders the error cleanly.
    browseFolders.mockResolvedValueOnce(HOME).mockRejectedValueOnce(new Error("nope"));
    render(<FolderExplorer onSelect={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("explorer-dir"));
    fireEvent.click(screen.getByTestId("explorer-dir"));
    expect(await screen.findByTestId("explorer-error")).toBeInTheDocument();
  });
});

describe("FolderExplorer — new folder", () => {
  beforeEach(() => {
    browseFolders.mockReset();
    makeFolder.mockReset();
  });

  it("creates a folder and descends into it", async () => {
    browseFolders
      .mockResolvedValueOnce(HOME)
      .mockResolvedValueOnce({
        path: "/home/u/NewProj",
        root: "/home/u",
        parent: "/home/u",
        dirs: [],
      });
    makeFolder.mockResolvedValue({ path: "/home/u/NewProj", name: "NewProj" });

    render(<FolderExplorer onSelect={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("explorer-newfolder-input"));

    fireEvent.change(screen.getByTestId("explorer-newfolder-input"), {
      target: { value: "NewProj" },
    });
    fireEvent.click(screen.getByTestId("explorer-newfolder-create"));

    await waitFor(() =>
      expect(makeFolder).toHaveBeenCalledWith("/home/u", "NewProj"),
    );
    await waitFor(() =>
      expect(browseFolders).toHaveBeenLastCalledWith("/home/u/NewProj"),
    );
  });

  it("shows an error when folder creation fails", async () => {
    browseFolders.mockResolvedValue(HOME);
    makeFolder.mockImplementation(async () => {
      throw new Error("nope");
    });
    render(<FolderExplorer onSelect={vi.fn()} onCancel={vi.fn()} />);
    await waitFor(() => screen.getByTestId("explorer-newfolder-input"));
    fireEvent.change(screen.getByTestId("explorer-newfolder-input"), {
      target: { value: "X" },
    });
    fireEvent.click(screen.getByTestId("explorer-newfolder-create"));
    expect(await screen.findByTestId("explorer-error")).toBeInTheDocument();
  });
});
