"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Fleuron } from "@/components/visual/Fleuron";
import { ThemeToggle } from "@/components/visual/ThemeToggle";
import { ProjectCard } from "@/components/launcher/ProjectCard";
import { FolderExplorer } from "@/components/launcher/FolderExplorer";
import {
  getLauncher,
  openProject,
  newProject,
  type LauncherProject,
} from "@/lib/api";

export default function LauncherPage() {
  const { t } = useTranslation();
  const [projects, setProjects] = useState<LauncherProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Where setup just wrote the global config (config.yaml / .env / agents).
  // Surfaced once after first-time setup so the on-disk location is discoverable
  // (on Windows it is %APPDATA%\armance, not the POSIX ~/.config/armance).
  const [configDir, setConfigDir] = useState<string | null>(null);

  useEffect(() => {
    getLauncher()
      .then((r) => setProjects(r.projects))
      .catch(() => setError(t("launcher:error.open_failed")))
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(() => {
    try {
      const dir = sessionStorage.getItem("armance.config-dir");
      if (dir) {
        setConfigDir(dir);
        sessionStorage.removeItem("armance.config-dir");
      }
    } catch {
      /* sessionStorage unavailable — non-fatal */
    }
  }, []);

  function goToProject(pid: string) {
    window.location.assign(`/projects/${pid}`);
  }

  async function handleOpen(project: LauncherProject) {
    setError(null);
    try {
      const opened = await openProject(project.path);
      goToProject(opened.id);
    } catch {
      setError(t("launcher:error.open_failed"));
    }
  }

  async function handleCreate(path: string) {
    setError(null);
    try {
      const created = await newProject(path);
      goToProject(created.id);
    } catch {
      setError(t("launcher:error.new_failed"));
      setPicking(false);
    }
  }

  return (
    <main className="launcher-root" data-testid="launcher-page">
      <header className="launcher-header">
        <ThemeToggle t={t} />
      </header>

      <section className="launcher-body">
        <Fleuron size="lg" />
        <h1 className="launcher-title" data-testid="launcher-title">
          {t("launcher:title")}
        </h1>
        <p className="launcher-subtitle">{t("launcher:subtitle")}</p>

        {error && (
          <p className="launcher-error" role="alert" data-testid="launcher-error">
            {error}
          </p>
        )}

        {configDir && (
          <p
            className="launcher-subtitle"
            data-testid="launcher-config-dir"
            style={{ fontFamily: "var(--ff-mono)", fontSize: "12px", color: "var(--ink-soft)" }}
          >
            {t("launcher:config_saved")} <span style={{ color: "var(--ink)" }}>{configDir}</span>
          </p>
        )}

        <div className="launcher-actions">
          <button
            type="button"
            className="btn-accent"
            data-testid="launcher-new"
            onClick={() => setPicking(true)}
          >
            {t("launcher:new_project")}
          </button>
        </div>

        {loading ? null : projects.length === 0 ? (
          <p className="launcher-empty" data-testid="launcher-empty">
            {t("launcher:no_projects")}
          </p>
        ) : (
          <ul className="launcher-grid" data-testid="launcher-list">
            {projects.map((p) => (
              <ProjectCard key={p.id} project={p} onOpen={handleOpen} />
            ))}
          </ul>
        )}
      </section>

      {picking && (
        <FolderExplorer
          onSelect={handleCreate}
          onCancel={() => setPicking(false)}
        />
      )}
    </main>
  );
}
