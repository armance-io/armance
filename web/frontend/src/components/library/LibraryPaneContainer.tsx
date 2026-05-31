"use client";

import { type FC } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  getLibrary,
  importDoc,
  deleteDoc,
  submitTurn,
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

  // Indexing runs asynchronously (agent turn), so poll a few times to catch
  // the status flip pending→indexed without forcing a manual refresh.
  const refetchSoon = () => {
    [800, 2000, 4000, 7000].forEach((ms) => setTimeout(() => refetch(), ms));
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

  const onIndex = async (name: string) => {
    await submitTurn(pid, sid, `/library-index ${name}`);
    toast(t("library:toast.indexing"), "info");
    refetchSoon();
  };

  const onLoad = async (name: string) => {
    await submitTurn(pid, sid, `/library-load ${name}`);
    toast(t("library:toast.loading"), "info");
    refetchSoon();
  };

  const onUnload = async (name: string) => {
    await submitTurn(pid, sid, `/library-unload ${name}`);
    refetchSoon();
  };

  const onUnindex = async (name: string) => {
    await submitTurn(pid, sid, `/library-unindex ${name}`);
    refetchSoon();
  };

  const onIndexAll = async () => {
    await submitTurn(pid, sid, `/library-index`);
    toast(t("library:toast.indexing_all"), "info");
    refetchSoon();
  };

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
      onImport={onImport}
      onDelete={onDelete}
      onIndex={onIndex}
      onLoad={onLoad}
      onUnload={onUnload}
      onUnindex={onUnindex}
      onIndexAll={onIndexAll}
      t={t}
    />
  );
};

export default LibraryPaneContainer;
