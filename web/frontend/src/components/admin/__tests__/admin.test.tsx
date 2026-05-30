import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ConfigForm, type ConfigValues } from "../ConfigForm";
import { SecretsList, type SecretEntry } from "../SecretsList";
import { AgentEditor, type AgentRecord } from "../AgentEditor";
import { AdminPageContainer } from "../AdminPageContainer";
import * as api from "@/lib/api";

const mockT = (key: string) => key;

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: mockT }),
}));

vi.mock("@/lib/api", () => ({
  getAdminConfig: vi.fn(),
  patchAdminConfig: vi.fn(),
  getAdminSecrets: vi.fn(),
  putAdminSecret: vi.fn(),
  deleteAdminSecret: vi.fn(),
  getAdminLogs: vi.fn(),
  patchLogLevel: vi.fn(),
  getAdminStats: vi.fn(),
  getAdminAgents: vi.fn(),
  patchAdminAgent: vi.fn(),
  getProviders: vi.fn(),
}));

vi.mock("@/lib/useLatestSession", () => ({
  useLatestSession: () => ({ pid: "default", sid: "default", loading: false }),
}));

describe("<ConfigForm />", () => {
  const defaultValues: ConfigValues = {
    default_provider: "openrouter",
    default_model: "gpt-4o",
    budget_effort: "low",
    language: "en",
    providers: [{ name: "openrouter", base_url: "https://openrouter.ai" }],
  };

  it("renders correctly with provided values", () => {
    render(
      <ConfigForm
        values={defaultValues}
        modelOptions={["gpt-4o", "claude-3-5"]}
        languageOptions={["en", "fr"]}
        onSave={vi.fn()}
        t={mockT}
      />
    );

    expect(screen.getByText("admin:config.title")).toBeDefined();
    expect(screen.getAllByText("openrouter").length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue("gpt-4o")).toBeDefined();
    expect(screen.getByDisplayValue("en")).toBeDefined();
  });

  it("validates empty required fields and displays errors", async () => {
    const handleSave = vi.fn();
    render(
      <ConfigForm
        values={{ ...defaultValues, default_model: "", language: "" }}
        modelOptions={[]}
        languageOptions={[]}
        onSave={handleSave}
        t={mockT}
      />
    );

    const saveBtn = screen.getByRole("button", { name: "admin:config.save" });
    fireEvent.click(saveBtn);

    expect(handleSave).not.toHaveBeenCalled();
    const errors = screen.getAllByText("admin:config.err.required");
    expect(errors.length).toBe(2);
  });

  it("calls onSave when form is submitted successfully", async () => {
    const handleSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ConfigForm
        values={defaultValues}
        modelOptions={["gpt-4o"]}
        languageOptions={["en"]}
        onSave={handleSave}
        t={mockT}
      />
    );

    const saveBtn = screen.getByRole("button", { name: "admin:config.save" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(handleSave).toHaveBeenCalledWith(defaultValues);
    });
  });

  it("allows clicking Chips to change budget", () => {
    render(
      <ConfigForm
        values={defaultValues}
        modelOptions={[]}
        languageOptions={[]}
        onSave={vi.fn()}
        t={mockT}
      />
    );

    const highChip = screen.getByText("admin:config.budget.high");
    fireEvent.click(highChip);
  });
});

describe("<SecretsList />", () => {
  const mockSecrets: SecretEntry[] = [
    { key: "OPENROUTER_API_KEY", value: "sk-or-v1-abcdef", last4: "cdef" },
  ];

  it("renders secret key and masked value", () => {
    render(
      <SecretsList
        secrets={mockSecrets}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReveal={vi.fn()}
        t={mockT}
      />
    );

    expect(screen.getByText("OPENROUTER_API_KEY")).toBeDefined();
    expect(screen.getByText("sk-***…cdef")).toBeDefined();
  });

  it("shows empty state when no secrets provided", () => {
    render(
      <SecretsList
        secrets={[]}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReveal={vi.fn()}
        t={mockT}
      />
    );

    expect(screen.getByText("admin:secrets.empty")).toBeDefined();
  });

  it("allows revealing value on click toggle", async () => {
    const handleReveal = vi.fn().mockResolvedValue("sk-or-v1-abcdef");
    render(
      <SecretsList
        secrets={mockSecrets}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReveal={handleReveal}
        t={mockT}
      />
    );

    const revealBtn = screen.getByLabelText("admin:secrets.action.reveal");
    
    fireEvent.click(revealBtn);
    await waitFor(() => {
      expect(handleReveal).toHaveBeenCalledWith("OPENROUTER_API_KEY");
      expect(screen.getByText("sk-or-v1-abcdef")).toBeDefined();
    });

    fireEvent.click(revealBtn);
    expect(screen.queryByText("sk-or-v1-abcdef")).toBeNull();
  });

  it("allows initiating edit and saving new value", async () => {
    const handleEdit = vi.fn().mockResolvedValue(undefined);
    render(
      <SecretsList
        secrets={mockSecrets}
        onEdit={handleEdit}
        onDelete={vi.fn()}
        onReveal={vi.fn()}
        t={mockT}
      />
    );

    const editBtn = screen.getByLabelText("admin:secrets.action.edit");
    fireEvent.click(editBtn);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "new-value-key" } });

    const saveBtn = screen.getByLabelText("admin:secrets.action.save");
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(handleEdit).toHaveBeenCalledWith("OPENROUTER_API_KEY", "new-value-key");
    });
  });

  it("allows cancelling editing", () => {
    render(
      <SecretsList
        secrets={mockSecrets}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onReveal={vi.fn()}
        t={mockT}
      />
    );

    const editBtn = screen.getByLabelText("admin:secrets.action.edit");
    fireEvent.click(editBtn);

    expect(screen.getByRole("textbox")).toBeDefined();

    const cancelBtn = screen.getByLabelText("admin:secrets.action.cancel");
    fireEvent.click(cancelBtn);

    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("opens delete confirm modal and executes delete on confirm", async () => {
    const handleDelete = vi.fn().mockResolvedValue(undefined);
    render(
      <SecretsList
        secrets={mockSecrets}
        onEdit={vi.fn()}
        onDelete={handleDelete}
        onReveal={vi.fn()}
        t={mockT}
      />
    );

    const deleteBtn = screen.getByLabelText("admin:secrets.action.delete");
    fireEvent.click(deleteBtn);

    expect(screen.getByText("admin:secrets.confirm_delete")).toBeDefined();

    const confirmBtn = screen.getByText("admin:secrets.action.delete");
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(handleDelete).toHaveBeenCalledWith("OPENROUTER_API_KEY");
    });
  });
});

describe("<AgentEditor />", () => {
  const mockAgents: AgentRecord[] = [
    {
      id: "agent-1",
      name: "Armance",
      role: "host",
      persona: "A friendly host agent.",
      portraitUrl: "/portraits/armance.png",
      provider: "openrouter",
      model: "gpt-4o",
      reasoning: "low",
      supportsReasoning: true,
    },
  ];

  it("renders agent records correctly", () => {
    render(
      <AgentEditor
        agents={mockAgents}
        providerOptions={["openrouter"]}
        modelOptionsByProvider={{ openrouter: ["gpt-4o"] }}
        onSave={vi.fn()}
        t={mockT}
      />
    );

    expect(screen.getByText("Armance")).toBeDefined();
    expect(screen.getByText("A friendly host agent.")).toBeDefined();
    expect(screen.getByDisplayValue("gpt-4o")).toBeDefined();
  });

  it("allows editing values and saving", async () => {
    const handleSave = vi.fn().mockResolvedValue(undefined);
    render(
      <AgentEditor
        agents={mockAgents}
        providerOptions={["openrouter", "gemini"]}
        modelOptionsByProvider={{ openrouter: ["gpt-4o"], gemini: ["gemini-flash"] }}
        onSave={handleSave}
        t={mockT}
      />
    );

    const selectElements = screen.getAllByRole("combobox");
    
    // Model Select
    fireEvent.change(selectElements[1]!, { target: { value: "gemini-flash" } });

    const saveBtn = screen.getByRole("button", { name: "admin:agents.save" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(handleSave).toHaveBeenCalled();
    });
  });
});

describe("<AdminPageContainer />", () => {
  const mockConfig = {
    default_provider: "openrouter",
    default_model: "gpt-4o",
    budget_effort: "low",
    language: "en",
    log_level: "info",
  };

  const mockSecretsList = [
    { name: "API_KEY_1", value: "sk-abcdef", set: true },
  ];

  const mockLogs = {
    lines: [
      { timestamp: "2026-01-01T00:00:00Z", agent: "Armance", event: "test-event" },
    ],
    total: 1,
    cursor: "next-cursor-val",
  };

  const mockStats = {
    agents: {
      Armance: { tokens_in: 100, tokens_out: 200, cost_usd: 0.05, msg_count: 5, avg_latency_ms: 200 },
    },
    global: {
      tokens_in: 100,
      tokens_out: 200,
      cost_usd: 0.05,
      msg_count: 5,
    },
  };

  const mockAgents = [
    { name: "Armance", domain: "host", role: "host", provider: "openrouter", model: "gpt-4o", reasoning: "low" },
  ];

  const mockProviderCatalogue = {
    providers: {
      openrouter: [{ id: "gpt-4o", name: "gpt-4o" }],
    },
  };

  beforeEach(() => {
    vi.mocked(api.getAdminConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.patchAdminConfig).mockResolvedValue(mockConfig);
    vi.mocked(api.getAdminSecrets).mockResolvedValue(mockSecretsList);
    vi.mocked(api.putAdminSecret).mockResolvedValue({ name: "NEW", set: true });
    vi.mocked(api.deleteAdminSecret).mockResolvedValue({ deleted: true });
    vi.mocked(api.getAdminLogs).mockResolvedValue(mockLogs);
    vi.mocked(api.patchLogLevel).mockResolvedValue({ level: "DEBUG" });
    vi.mocked(api.getAdminStats).mockResolvedValue(mockStats);
    vi.mocked(api.getAdminAgents).mockResolvedValue(mockAgents);
    vi.mocked(api.getProviders).mockResolvedValue(mockProviderCatalogue);
  });

  it("switches tabs and fetches corresponding backend data", async () => {
    render(<AdminPageContainer pid="default" t={mockT} />);

    // Renders config tab by default
    await waitFor(() => {
      expect(api.getAdminConfig).toHaveBeenCalledWith("default");
    });

    // 1. Secrets Tab
    const secretsTabBtn = screen.getByRole("tab", { name: "admin:tabs.secrets" });
    fireEvent.click(secretsTabBtn);
    await waitFor(() => {
      expect(api.getAdminSecrets).toHaveBeenCalledWith("default");
    });
    expect(screen.getByText("API_KEY_1")).toBeDefined();

    // 2. Logs Tab
    const logsTabBtn = screen.getByRole("tab", { name: "admin:tabs.logs" });
    fireEvent.click(logsTabBtn);
    await waitFor(() => {
      expect(api.getAdminLogs).toHaveBeenCalledWith("default", { limit: 50 });
    });

    // 3. Stats Tab
    const statsTabBtn = screen.getByRole("tab", { name: "admin:tabs.stats" });
    fireEvent.click(statsTabBtn);
    await waitFor(() => {
      expect(api.getAdminStats).toHaveBeenCalledWith("default");
    });

    // 4. Agents Tab
    const agentsTabBtn = screen.getByRole("tab", { name: "admin:tabs.agents" });
    fireEvent.click(agentsTabBtn);
    await waitFor(() => {
      expect(api.getAdminAgents).toHaveBeenCalledWith("default", "default");
    });
  });

  it("handles loopback only 403 error gracefully in Secrets tab", async () => {
    vi.mocked(api.getAdminSecrets).mockRejectedValue({ status: 403 });
    render(<AdminPageContainer pid="default" t={mockT} />);

    const secretsTabBtn = screen.getByRole("tab", { name: "admin:tabs.secrets" });
    fireEvent.click(secretsTabBtn);

    await waitFor(() => {
      expect(screen.getByText("admin:secrets.localhost_only")).toBeDefined();
    });
  });

  it("handles offline state gracefully in Secrets tab", async () => {
    // Simulate non-loopback window hostname and navigator.onLine as false
    Object.defineProperty(window, "location", {
      value: { hostname: "app.armance.io" },
      writable: true,
      configurable: true,
    });
    Object.defineProperty(navigator, "onLine", {
      value: false,
      writable: true,
      configurable: true,
    });

    render(<AdminPageContainer pid="default" t={mockT} />);

    const secretsTabBtn = screen.getByRole("tab", { name: "admin:tabs.secrets" });
    fireEvent.click(secretsTabBtn);

    await waitFor(() => {
      expect(screen.getByText("admin:secrets.offline")).toBeDefined();
    });
  });
});
