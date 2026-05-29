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

export interface LibraryPaneContainerProps {
  pid: string;
  sid: string;
}

export const LibraryPaneContainer: FC<LibraryPaneContainerProps> = ({
  pid,
  sid,
}) => {
  const { t } = useTranslation();

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

  const onImport = async (file: File) => {
    await importDoc(pid, sid, file, false);
    refetch();
  };

  const onDelete = async (name: string) => {
    await deleteDoc(pid, sid, name, true);
    refetch();
  };

  const onIndex = async (name: string) => {
    await submitTurn(pid, sid, `/library-index ${name}`);
    refetch();
  };

  const onLoad = async (name: string) => {
    await submitTurn(pid, sid, `/library-load ${name}`);
    refetch();
  };

  const onUnload = async (name: string) => {
    await submitTurn(pid, sid, `/library-unload ${name}`);
    refetch();
  };

  const onUnindex = async (name: string) => {
    await submitTurn(pid, sid, `/library-unindex ${name}`);
    refetch();
  };

  const onIndexAll = async () => {
    await submitTurn(pid, sid, `/library-index`);
    refetch();
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
