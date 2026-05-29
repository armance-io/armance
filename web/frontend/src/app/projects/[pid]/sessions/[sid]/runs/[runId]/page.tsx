"use client";

import { use } from "react";
import { useTranslation } from "react-i18next";
import { AppShell } from "@/components/visual/AppShell";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import { LivePanel } from "@/components/run/LivePanel";

interface RunPageProps {
  params: Promise<{
    pid: string;
    sid: string;
    runId: string;
  }>;
}

export default function RunPage({ params }: RunPageProps) {
  const { pid, sid, runId } = use(params);
  const { t } = useTranslation();

  // Custom translation function to handle nested mode keys and fall back safely
  const customT = (key: string): string => {
    if (key === "run:panel.mode.interactive") return "interactive";
    if (key === "run:panel.mode.autonomous") return "autonomous";
    if (key === "run:panel.deliverable") return "Deliverable";
    if (key === "run:panel.arguments") return "Arguments";
    if (key === "run:panel.sources") return "Sources";
    if (key === "run:panel.hypotheses") return "Hypotheses";
    if (key === "run:panel.downloads") return "Downloads";
    if (key === "run:ledger.retained") return "Retained";
    if (key === "run:ledger.rejected") return "Rejected";
    if (key === "run:ledger.proposed_by") return "Proposed by";
    if (key === "run:ledger.rejected_by") return "Rejected by";
    if (key === "hypotheses:title") return "Hypotheses held by Mona";
    if (key === "hypotheses:marker") return "Hypothesis";
    if (key === "hypotheses:invalidator") return "invalidator";
    return t(key);
  };

  // High-fidelity fixture data for wiring validation (Phase 1 preview)
  const deliverable = {
    title: "Synthèse de délibération — VApp Dossier",
    markdown: "# Synthèse Finale\n\nVoici le rapport final de délibération.",
    downloadUrl: `/api/projects/${pid}/sessions/${sid}/workflows/default/runs/${runId}/deliverable`,
    format: "md" as const,
  };

  const mockArguments = [
    {
      id: "a_001",
      claim: "Lancer en mode réduit limite le risque marque.",
      status: "retained" as const,
      proposed_by: ["Sarah", "Julian"],
      proposed_in_steps: ["analyse_a", "analyse_b"],
      sources: ["s_001"],
      weight: 0.75,
    },
    {
      id: "a_002",
      claim: "Lancer en mode complet sans étude préalable.",
      status: "rejected" as const,
      proposed_by: ["Aisha"],
      proposed_in_steps: ["analyse_a"],
      rejected_by: "Serge",
      rejection_reason: "Hypothèse non sourcée ; counter-sample 2024-Q3.",
      sources: [],
      weight: 0.15,
    },
  ];

  const mockSources = [
    {
      id: "s_001",
      kind: "doc" as const,
      ref: "docs/report-2024.pdf",
      label: "Rapport financier 2024 (PDF)",
    },
    {
      id: "s_002",
      kind: "web" as const,
      ref: "https://example.org/article",
      label: "Article de presse",
    },
  ];

  const mockHypotheses = [
    {
      step_id: "step-1",
      text: "Mona a posé l'hypothèse d'une réduction des coûts.",
      invalidator: "inval-1",
    },
  ];

  const mockDownloads = [
    { format: "MD", url: "#" },
    { format: "PDF", url: "#" },
  ];

  return (
    <AppShell
      sidebar={
        <EmptyShell
          title={t("visual:empty.shell.title")}
          hint={t("visual:empty.shell.hint")}
        />
      }
      t={t}
    >
      <div style={{ display: "flex", width: "100%", height: "100%" }}>
        <div style={{ flex: 1, padding: "24px", color: "var(--ink-soft)" }}>
          <h2>{t("runs:detail.steps")}</h2>
          <p>Run: {runId}</p>
        </div>
        <LivePanel
          mode="autonomous"
          deliverable={deliverable}
          arguments={mockArguments}
          sources={mockSources}
          hypotheses={mockHypotheses}
          downloads={mockDownloads}
          t={customT}
        />
      </div>
    </AppShell>
  );
}
