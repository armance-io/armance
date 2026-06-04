"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ensureI18n } from "@/lib/i18n";
import { getAdminConfig } from "@/lib/api";

export function I18nBootstrap({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const i18n = ensureI18n();

    // Skip backend configuration check in E2E test environments to avoid network timeouts
    const isE2E = typeof window !== "undefined" && (window.navigator.webdriver || window.location.search.includes("e2e=true"));
    if (isE2E) {
      setMounted(true);
      return;
    }

    // Apply the configured UI language so menus follow it (was stuck on EN).
    void getAdminConfig("default")
      .then((cfg) => {
        const lang = typeof cfg.language === "string" ? cfg.language : "";
        if (lang && lang !== i18n.language) void i18n.changeLanguage(lang);
      })
      .catch(() => {/* keep default */})
      .finally(() => setMounted(true));
  }, []);

  if (!mounted) {
    return null; // Prevents SSR/hydration mismatch with translation keys before mounting
  }

  return <>{children}</>;
}
