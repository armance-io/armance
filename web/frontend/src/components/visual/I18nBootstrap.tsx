"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ensureI18n } from "@/lib/i18n";

export function I18nBootstrap({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    ensureI18n();
    setMounted(true);
  }, []);

  if (!mounted) {
    return null; // Prevents SSR/hydration mismatch with translation keys before mounting
  }

  return <>{children}</>;
}
