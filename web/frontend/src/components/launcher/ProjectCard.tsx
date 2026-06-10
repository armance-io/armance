"use client";

import { useTranslation } from "react-i18next";

import type { LauncherProject } from "@/lib/api";

export interface ProjectCardProps {
  project: LauncherProject;
  onOpen: (project: LauncherProject) => void;
}

/** A parchment card for one known project (DESIGN.md: sharp corners, violet accent). */
export function ProjectCard({ project, onOpen }: ProjectCardProps) {
  const { t } = useTranslation();
  const stale = !project.exists;

  return (
    <li
      className={`project-card${stale ? " project-card--stale" : ""}`}
      data-testid="project-card"
      data-pid={project.id}
    >
      <div className="project-card__body">
        <h2 className="project-card__name">{project.name}</h2>
        <p className="project-card__path" title={project.path}>
          {project.path}
        </p>
        {stale && (
          <p className="project-card__stale" title={t("launcher:stale_hint")}>
            {t("launcher:stale")}
          </p>
        )}
      </div>
      <button
        type="button"
        className="btn-accent project-card__open"
        data-testid="project-open"
        disabled={stale}
        onClick={() => onOpen(project)}
      >
        {t("launcher:open")}
      </button>
    </li>
  );
}
