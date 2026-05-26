"use client";

/**
 * HypothesisListContainer — fetches Mona's autonomous-mode hypothesis
 * markers from the backend and renders <HypothesisList />.
 *
 * Spec: web-c-deliberation.md § C.10
 *       web-v2-wire-prompts.md  § C-WIRE.4
 */

import { type FC, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { listHypotheses } from "@/lib/api";
import { HypothesisList } from "./HypothesisList";

interface HypothesisView {
  step_id: string;
  text: string;
  // invalidator is reserved — the backend doesn't extract it yet but the
  // visual component accepts it; we pass it through when present.
  invalidator?: string;
}

export interface HypothesisListContainerProps {
  pid: string;
  sid: string;
  workflow: string;
  runId: string;
}

export const HypothesisListContainer: FC<HypothesisListContainerProps> = ({
  pid,
  sid,
  workflow,
  runId,
}) => {
  const { t } = useTranslation();
  const [items, setItems] = useState<HypothesisView[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await listHypotheses(pid, sid, workflow, runId);
        if (cancelled) return;
        setItems(res.hypotheses.map((h) => ({ step_id: h.step_id, text: h.text })));
      } catch {
        if (cancelled) return;
        setItems([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pid, sid, workflow, runId]);

  if (items === null) return null;
  return <HypothesisList hypotheses={items} t={t} />;
};

export default HypothesisListContainer;
