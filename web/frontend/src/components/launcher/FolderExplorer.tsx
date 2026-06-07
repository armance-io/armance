"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { browseFolders, type BrowseResult } from "@/lib/api";

export interface FolderExplorerProps {
  onSelect: (path: string) => void;
  onCancel: () => void;
}

/**
 * Minimal server-side folder picker (DESIGN.md parchment modal). Starts at the
 * user's home dir, descends one level at a time, and never traverses above the
 * root the backend enforces.
 */
export function FolderExplorer({ onSelect, onCancel }: FolderExplorerProps) {
  const { t } = useTranslation();
  const [view, setView] = useState<BrowseResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load(path?: string) {
    setError(null);
    browseFolders(path)
      .then((r) => setView(r))
      .catch(() => setError(t("launcher:error.browse_failed")));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="explorer-overlay" data-testid="folder-explorer" role="dialog" aria-modal="true">
      <div className="explorer-card">
        <h2 className="explorer-title">{t("launcher:browse.title")}</h2>
        <p className="explorer-current" data-testid="explorer-path">
          {view?.path ?? "…"}
        </p>

        {error && (
          <p className="launcher-error" role="alert" data-testid="explorer-error">
            {error}
          </p>
        )}

        <div className="explorer-list" data-testid="explorer-list">
          {view?.parent && (
            <button
              type="button"
              className="explorer-row explorer-row--up"
              data-testid="explorer-up"
              onClick={() => load(view.parent ?? undefined)}
            >
              ↑ {t("launcher:browse.up")}
            </button>
          )}
          {view && view.dirs.length === 0 && (
            <p className="explorer-empty">{t("launcher:browse.empty")}</p>
          )}
          {view?.dirs.map((d) => (
            <button
              type="button"
              key={d.path}
              className="explorer-row"
              data-testid="explorer-dir"
              onClick={() => load(d.path)}
            >
              {d.name}
            </button>
          ))}
        </div>

        <p className="explorer-hint">{t("launcher:browse.create_hint")}</p>

        <div className="explorer-actions">
          <button
            type="button"
            className="btn-ghost"
            data-testid="explorer-cancel"
            onClick={onCancel}
          >
            {t("launcher:browse.cancel")}
          </button>
          <button
            type="button"
            className="btn-accent"
            data-testid="explorer-select"
            disabled={!view}
            onClick={() => view && onSelect(view.path)}
          >
            {t("launcher:browse.use_this")}
          </button>
        </div>
      </div>
    </div>
  );
}
