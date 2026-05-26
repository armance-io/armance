"use client";

import { useTranslation } from "react-i18next";
import { useEffect } from "react";
import { ensureI18n } from "@/lib/i18n";

export default function HomePage() {
  useEffect(() => {
    ensureI18n();
  }, []);
  const { t } = useTranslation();
  return (
    <main style={{ padding: 32, fontFamily: "var(--ff-serif)" }}>
      <h1 style={{ fontSize: 48, margin: 0 }}>{t("app:title")}</h1>
      <p style={{ color: "var(--ink-soft)", marginTop: 8 }}>{t("app:tagline")}</p>
    </main>
  );
}
