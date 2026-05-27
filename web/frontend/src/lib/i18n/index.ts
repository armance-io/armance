"use client";

import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "@/locales/en/common.json";
import fr from "@/locales/fr/common.json";

const NAMESPACES = [
  "common",
  "visual",
  "library",
  "chat",
  "checkpoint",
  "panel",
  "render",
  "runs",
  "run",
  "workflow",
  "hypotheses",
  "sidebar",
  "admin",
  "audio",
  "setup",
] as const;

export type Namespace = typeof NAMESPACES[number];

let initialised = false;

export function ensureI18n(language: string = "en"): typeof i18n {
  if (initialised) return i18n;
  void i18n.use(initReactI18next).init({
    lng: language,
    fallbackLng: "en",
    ns: NAMESPACES as readonly string[] as string[],
    defaultNS: "common",
    interpolation: { escapeValue: false },
    resources: {
      en: { common: en },
      fr: { common: fr },
    },
  });
  initialised = true;
  return i18n;
}
