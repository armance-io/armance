"use client";

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { EmptyShell } from "@/components/visual/EmptyState/EmptyShell";
import { DeliverablesTabContainer } from "@/components/sidebar/DeliverablesTabContainer";
import { DeliverableReader } from "@/components/library/DeliverableReader";
import { api } from "@/lib/api";
import { useRouteParams } from "@/lib/routeParams";

interface DeliverableItem {
  id: string;
  title: string;
  kind: "synthesis" | "mona-deliverable" | "export";
  format: "md" | "pdf" | "docx" | "pptx";
  workflow?: string;
  run_id?: string;
  created_at: string;
  starred: boolean;
}

export default function DeliverablesView() {
  const { pid, sid } = useRouteParams();
  const { t } = useTranslation();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [markdown, setMarkdown] = useState<string>("");
  const [loadingContent, setLoadingContent] = useState(false);

  // Fetch the list of deliverables
  const { data: deliverables = [] } = useQuery<DeliverableItem[]>({
    queryKey: ["deliverables", pid, sid],
    queryFn: () => api.get<DeliverableItem[]>(`/projects/${pid}/sessions/${sid}/deliverables`),
    enabled: Boolean(pid && sid),
  });

  // Auto-select the first deliverable if none is selected
  useEffect(() => {
    if (!selectedId && deliverables.length > 0) {
      const first = deliverables[0];
      if (first) {
        setSelectedId(first.id);
      }
    }
  }, [deliverables, selectedId]);

  const selectedItem = deliverables.find((d) => d.id === selectedId);

  useEffect(() => {
    if (!selectedId || !selectedItem) {
      setMarkdown("");
      return;
    }

    const selId = selectedId;
    const item = selectedItem;

    async function fetchContent() {
      setLoadingContent(true);
      try {
        // If it's a binary export, try fetching the sibling synthesis.md for reading,
        // otherwise load the file itself.
        let fetchId = selId;
        if (item.format !== "md" && item.kind === "export") {
          const parts = selId.split("/");
          if (parts.length > 1) {
            parts[parts.length - 1] = "synthesis.md";
            fetchId = parts.join("/");
          }
        }

        const res = await api.raw(`/projects/${pid}/sessions/${sid}/exports/${encodeURIComponent(fetchId)}`);
        if (res.ok) {
          const text = await res.text();
          setMarkdown(text);
        } else {
          if (item.format !== "md") {
            setMarkdown(`# ${item.title}\n\nBinary deliverable (${item.format}). Please use the download button above to retrieve it.`);
          } else {
            setMarkdown(`# Error\nFailed to load content.`);
          }
        }
      } catch {
        setMarkdown(`# Error\nFailed to load content.`);
      } finally {
        setLoadingContent(false);
      }
    }

    void fetchContent();
  }, [selectedId, selectedItem, pid, sid, t]);

  const downloadUrl = selectedId
    ? `/api/projects/${pid}/sessions/${sid}/exports/${encodeURIComponent(selectedId)}`
    : "";

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div style={{
        width: "280px",
        flexShrink: 0,
        borderRight: "1px solid var(--rule, #d6c8ad)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "var(--bg-paper, #f4ede0)"
      }}>
        <div style={{
          fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
          fontSize: "18px",
          fontWeight: 600,
          color: "var(--ink, #2a2520)",
          padding: "16px",
          borderBottom: "1px solid var(--rule, #d6c8ad)",
        }}>
          {t("sidebar:tabs.deliverables")}
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <DeliverablesTabContainer
            pid={pid}
            sid={sid}
            onOpen={(id) => setSelectedId(id)}
          />
        </div>
      </div>

      <div style={{ flex: 1, height: "100%", overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {loadingContent ? (
          <div style={{ padding: "20px", color: "var(--ink-soft)" }}>
            {t("app:loading")}
          </div>
        ) : selectedItem ? (
          <DeliverableReader
            title={selectedItem.title}
            markdown={markdown}
            downloadUrl={downloadUrl}
            downloadFormat={selectedItem.format}
            sourcePath={selectedItem.id}
            t={t}
          />
        ) : (
          <EmptyShell
            title={t("visual:empty.shell.title")}
            hint={t("visual:empty.shell.hint")}
          />
        )}
      </div>
    </div>
  );
}
