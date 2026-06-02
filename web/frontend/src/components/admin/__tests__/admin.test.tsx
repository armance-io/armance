import { describe, it, expect, vi, beforeEach } from "vitest";
import { render as rtlRender, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactElement } from "react";

// LogsTab/StatsTab/etc. use react-query; provide a client for every render.
function render(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return rtlRender(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}
import { ConfigForm, type ConfigValues } from "../ConfigForm";

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
        providerOptions={["openrouter", "claude-code"]}
        languageOptions={["en", "fr"]}
        onSave={vi.fn()}
        t={mockT}
      />
    );

    expect(screen.getByText("admin:config.title")).toBeDefined();
    // Provider id is shown via providerLabel (openrouter → "OpenRouter").
    expect(screen.getAllByText("OpenRouter").length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue("en")).toBeDefined();
  });

  it("validates empty required fields and displays errors", async () => {
    const handleSave = vi.fn();
    render(
      <ConfigForm
        values={{ ...defaultValues, language: "" }}
        providerOptions={["openrouter"]}
        languageOptions={[]}
        onSave={handleSave}
        t={mockT}
      />
    );

    const saveBtn = screen.getByRole("button", { name: "admin:config.save" });
    fireEvent.click(saveBtn);

    expect(handleSave).not.toHaveBeenCalled();
    const errors = screen.getAllByText("admin:config.err.required");
    expect(errors.length).toBe(1);
  });

  it("calls onSave when form is submitted successfully", async () => {
    const handleSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ConfigForm
        values={defaultValues}
        providerOptions={["openrouter"]}
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
        providerOptions={["openrouter"]}
        languageOptions={[]}
        onSave={vi.fn()}
        t={mockT}
      />
    );

    const highChip = screen.getByText("admin:config.budget.high");
    fireEvent.click(highChip);
  });

  it("expands a provider to show inline secrets", () => {
    const secrets = [
      { name: "OPENROUTER_API_KEY", value: "sk-or-abc", set: true },
    ];
    render(
      <ConfigForm
        values={defaultValues}
        providerOptions={["openrouter"]}
        languageOptions={["en"]}
        onSave={vi.fn()}
        secrets={secrets}
        t={mockT}
      />
    );

    // Provider row should be present with collapse arrow
    const expandBtns = screen.getAllByText("▸");
    expect(expandBtns.length).toBeGreaterThan(0);
    fireEvent.click(expandBtns[0]!);

    // After expanding, the secret key name should be visible
    expect(screen.getByText("OPENROUTER_API_KEY")).toBeDefined();
  });

  it("does not show trash icon when only one provider configured", () => {
    render(
      <ConfigForm
        values={defaultValues}
        providerOptions={["openrouter", "gemini"]}
        languageOptions={["en"]}
        onSave={vi.fn()}
        t={mockT}
      />
    );

    // With only 1 provider, the trash icon should not appear
    const trashButtons = screen.queryAllByTitle("admin:config.delete_provider");
    expect(trashButtons.length).toBe(0);
  });

  it("shows the add provider button when unregistered providers exist", () => {
    render(
      <ConfigForm
        values={defaultValues}
        providerOptions={["openrouter", "gemini", "claude-code"]}
        languageOptions={["en"]}
        onSave={vi.fn()}
        t={mockT}
      />
    );

    // Button to add a new provider should be visible
    const addBtn = screen.getByText("admin:config.add_provider");
    expect(addBtn).toBeDefined();
    fireEvent.click(addBtn);

    // The inline form should now be visible with a select
    expect(screen.getByText("Select Provider")).toBeDefined();
  });

  it("renders claude-code provider without API key fields", () => {
    const valuesWithClaude: ConfigValues = {
      ...defaultValues,
      providers: [
        { name: "openrouter", base_url: "https://openrouter.ai" },
        { name: "claude-code" },
      ],
    };
    render(
      <ConfigForm
        values={valuesWithClaude}
        providerOptions={["openrouter", "claude-code"]}
        languageOptions={["en"]}
        onSave={vi.fn()}
        t={mockT}
      />
    );

    // Expand the claude-code provider
    const expandBtns = screen.getAllByText("▸");
    // Claude Subscription should be second
    fireEvent.click(expandBtns[1]!);

    // Should show the subscription auth message
    expect(screen.getByText(/No API Key required/)).toBeDefined();
  });

  it("shows trash icon when multiple providers are configured", () => {
    const multiProvValues: ConfigValues = {
      ...defaultValues,
      providers: [
        { name: "openrouter", base_url: "https://openrouter.ai" },
        { name: "gemini" },
      ],
    };
    render(
      <ConfigForm
        values={multiProvValues}
        providerOptions={["openrouter", "gemini"]}
        languageOptions={["en"]}
        onSave={vi.fn()}
        t={mockT}
      />
    );

    const trashButtons = screen.queryAllByTitle("admin:config.delete_provider");
    expect(trashButtons.length).toBe(2);
  });

  it("allows editing a secret inline and saving", async () => {
    const secrets = [
      { name: "OPENROUTER_API_KEY", value: "sk-or-abc", set: true },
    ];
    const onEditSecret = vi.fn().mockResolvedValue(undefined);
    render(
      <ConfigForm
        values={defaultValues}
        providerOptions={["openrouter"]}
        languageOptions={["en"]}
        onSave={vi.fn()}
        secrets={secrets}
        onEditSecret={onEditSecret}
        t={mockT}
      />
    );

    // Expand the provider
    fireEvent.click(screen.getAllByText("▸")[0]!);

    // Click the edit button (✎)
    const editBtns = screen.getAllByTitle("admin:secrets.action.edit");
    fireEvent.click(editBtns[0]!);

    // Save button (✓) and cancel (✕) should appear
    expect(screen.getByTitle("admin:secrets.action.save")).toBeDefined();
    expect(screen.getByTitle("admin:secrets.action.cancel")).toBeDefined();

    // Click save
    fireEvent.click(screen.getByTitle("admin:secrets.action.save"));
    await waitFor(() => {
      expect(onEditSecret).toHaveBeenCalled();
    });
  });

  it("reveals a secret in ElegantPopup on eye icon click", async () => {
    const secrets = [
      { name: "OPENROUTER_API_KEY", value: "sk-or-v1-fullkey123", set: true },
    ];
    render(
      <ConfigForm
        values={defaultValues}
        providerOptions={["openrouter"]}
        languageOptions={["en"]}
        onSave={vi.fn()}
        secrets={secrets}
        t={mockT}
      />
    );

    // Expand the provider
    fireEvent.click(screen.getAllByText("▸")[0]!);

    // Click the reveal button
    const revealBtns = screen.getAllByTitle("admin:secrets.action.reveal");
    fireEvent.click(revealBtns[0]!);

    // The ElegantPopup should show the full value
    await waitFor(() => {
      expect(screen.getByText("sk-or-v1-fullkey123")).toBeDefined();
    });
  });

  it("adds a provider via the inline form and calls onAddProviderSecrets", async () => {
    const onAddProviderSecrets = vi.fn().mockResolvedValue(undefined);
    render(
      <ConfigForm
        values={defaultValues}
        providerOptions={["openrouter", "gemini"]}
        languageOptions={["en"]}
        onSave={vi.fn()}
        onAddProviderSecrets={onAddProviderSecrets}
        t={mockT}
      />
    );

    // Click "Add Provider"
    const addBtn = screen.getByText("admin:config.add_provider");
    fireEvent.click(addBtn);

    // Select Gemini from the dropdown
    const select = screen.getAllByRole("combobox")[0]!;
    fireEvent.change(select, { target: { value: "gemini" } });

    // Click the "+ Add Provider" submit button
    const submitBtn = screen.getByText("+ Add Provider");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onAddProviderSecrets).toHaveBeenCalled();
    });
  });

  it("cancel button in edit mode returns to display mode", () => {
    const secrets = [
      { name: "OPENROUTER_API_KEY", value: "sk-or-abc", set: true },
    ];
    render(
      <ConfigForm
        values={defaultValues}
        providerOptions={["openrouter"]}
        languageOptions={["en"]}
        onSave={vi.fn()}
        secrets={secrets}
        t={mockT}
      />
    );

    // Expand and enter edit mode
    fireEvent.click(screen.getAllByText("▸")[0]!);
    fireEvent.click(screen.getAllByTitle("admin:secrets.action.edit")[0]!);

    // Click cancel
    fireEvent.click(screen.getByTitle("admin:secrets.action.cancel"));

    // Should be back to display mode — edit buttons visible again
    expect(screen.getAllByTitle("admin:secrets.action.edit").length).toBeGreaterThan(0);
  });

  it("shows placeholder for unconfigured secret", () => {
    // Secrets array is empty — the provider has no configured API key
    render(
      <ConfigForm
        values={defaultValues}
        providerOptions={["openrouter"]}
        languageOptions={["en"]}
        onSave={vi.fn()}
        secrets={[]}
        t={mockT}
      />
    );

    // Expand the provider
    fireEvent.click(screen.getAllByText("▸")[0]!);

    // Should show "(not configured)" placeholder
    expect(screen.getByText("(not configured)")).toBeDefined();
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

  const mockSecrets = [
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
    vi.mocked(api.getAdminSecrets).mockResolvedValue(mockSecrets);
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

    // 1. Logs Tab
    const logsTabBtn = screen.getByRole("tab", { name: "admin:tabs.logs" });
    fireEvent.click(logsTabBtn);
    await waitFor(() => {
      expect(api.getAdminLogs).toHaveBeenCalledWith("default", { limit: 50 });
    });

    // 2. Stats Tab
    const statsTabBtn = screen.getByRole("tab", { name: "admin:tabs.stats" });
    fireEvent.click(statsTabBtn);
    await waitFor(() => {
      expect(api.getAdminStats).toHaveBeenCalledWith("default");
    });

    // 3. Agents Tab
    const agentsTabBtn = screen.getByRole("tab", { name: "admin:tabs.agents" });
    fireEvent.click(agentsTabBtn);
    await waitFor(() => {
      expect(api.getAdminAgents).toHaveBeenCalledWith("default", "default");
    });
  });

  it("loads secrets alongside config on the Config tab", async () => {
    render(<AdminPageContainer pid="default" t={mockT} />);

    // The Config tab is default — it should fetch secrets as part of its mount.
    await waitFor(() => {
      expect(api.getAdminSecrets).toHaveBeenCalled();
    });
  });
});
