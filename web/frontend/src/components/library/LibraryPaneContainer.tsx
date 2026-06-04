"use client";

import { type FC } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";
import {
  getLibrary,
  importDoc,
  deleteDoc,
  libraryAction,
  getEmbeddingModels,
  patchAdminConfig,
  type EmbeddingModel,
} from "@/lib/api";
import { LibraryPane } from "./LibraryPane";
import { useToast } from "@/components/_shared/Toast";

export interface LibraryPaneContainerProps {
  pid: string;
  sid: string;
}

export const LibraryPaneContainer: FC<LibraryPaneContainerProps> = ({
  pid,
  sid,
}) => {
  const { t } = useTranslation();
  const { toast } = useToast();

  const {
    data,
    refetch,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["library", pid, sid],
    queryFn: () => getLibrary(pid, sid),
  });

  const docs = data?.docs ?? [];
  const totalFeuillets = data?.total_feuillets ?? 0;
  const embeddingAvailable = Boolean(data?.embedding_model);

  // Embedding catalogue for the inline picker shown when no model is set yet,
  // so the user can enable indexing from the library without leaving for admin.
  const [embeddingOptions, setEmbeddingOptions] = useState<EmbeddingModel[]>([]);
  useEffect(() => {
    let cancelled = false;
    void getEmbeddingModels()
      .then((res) => {
        if (!cancelled) setEmbeddingOptions(res.models ?? []);
      })
      .catch(() => {
        /* best-effort — free text still works */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onSetEmbedding = async (provider: string, model: string) => {
    try {
      await patchAdminConfig(pid, {
        embedding_provider: provider,
        embedding_model: model,
      });
      toast(t("library:toast.embedding_set"), "success");
      refetch();
    } catch {
      toast(t("common:error"), "error");
    }
  };

  const onImport = async (file: File) => {
    await importDoc(pid, sid, file, false);
    toast(t("library:toast.imported"), "success");
    refetch();
  };

  const onDelete = async (name: string) => {
    await deleteDoc(pid, sid, name, true);
    refetch();
  };

  // Prominent "indexing in progress" state — the per-row spinner alone was too
  // discreet. Drives a banner in the library while an index action runs.
  const [indexing, setIndexing] = useState(false);

  // Library mutations now run synchronously via the dedicated action route
  // (no LLM turn, no conversation entry). Returns the ok flag so the button
  // can flash an ephemeral check on success; errors surface as elegant toasts.
  const run = async (
    action: "index" | "load" | "unload" | "unindex",
    name?: string,
  ): Promise<boolean> => {
    const isIndex = action === "index";
    if (isIndex) setIndexing(true);
    try {
      const res = await libraryAction(pid, sid, action, name);
      if (!res.ok) {
        toast(res.message || t("common:error"), "error");
        return false;
      }
      // One elegant toast per (re)indexed document.
      (res.indexed_docs ?? []).forEach((doc) =>
        toast(t("library:toast.doc_indexed").replace("{name}", doc), "success"),
      );
      refetch();
      return true;
    } catch {
      toast(t("common:error"), "error");
      return false;
    } finally {
      if (isIndex) setIndexing(false);
    }
  };

  const onIndex = (name: string) => run("index", name);
  const onLoad = (name: string) => run("load", name);
  const onUnload = (name: string) => run("unload", name);
  const onUnindex = (name: string) => run("unindex", name);
  const onIndexAll = () => run("index");

  if (isLoading) {
    return (
      <div style={{ padding: "20px", color: "var(--ink-soft)" }}>
        {t("app:loading")}
      </div>
    );
  }

  if (isError) {
    return (
      <div style={{ padding: "20px", color: "oklch(0.42 0.14 22)" }}>
        {t("common:error")}
      </div>
    );
  }

  return (
    <LibraryPane
      docs={docs}
      totalFeuillets={totalFeuillets}
      embeddingAvailable={embeddingAvailable}
      onImport={onImport}
      onDelete={onDelete}
      onIndex={onIndex}
      onLoad={onLoad}
      onUnload={onUnload}
      onUnindex={onUnindex}
      onIndexAll={onIndexAll}
      embeddingOptions={embeddingOptions}
      onSetEmbedding={onSetEmbedding}
      indexing={indexing}
      t={t}
    />
  );
};

export default LibraryPaneContainer;
