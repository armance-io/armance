import { type FC, useState } from "react";
import { EmptyShell } from "./EmptyShell";
import { triggerPrefill } from "@/lib/prefillBus";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface EmptySessionProps {
  /**
   * i18n accessor. Keys consumed:
   *   visual:empty.session.title
   *   visual:empty.session.hint
   *   visual:empty.session.cta
   *   visual:empty.session.suggestion_decision
   *   visual:empty.session.suggestion_document
   */
  t: (key: string) => string;
  /** Optional action — typically "drop a document" or "show prompts". */
  onCta?: () => void;
  /**
   * Suggestion handlers. The two suggestions have distinct destinations:
   *   - decision → start the conversation (prefill the chat input)
   *   - document → open the Library
   * When omitted, both fall back to prefilling the chat input (legacy behavior),
   * which only works where a prefill listener is mounted (an active session).
   */
  onSuggestDecision?: (text: string) => void;
  onSuggestDocument?: (text: string) => void;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

/**
 * `<EmptySession />` — chat-pane state shown before the first message.
 */
export const EmptySession: FC<EmptySessionProps> = ({
  t,
  onCta,
  onSuggestDecision,
  onSuggestDocument,
}) => {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const suggestions = [
    {
      text: t("visual:empty.session.suggestion_decision"),
      onSelect: onSuggestDecision ?? triggerPrefill,
    },
    {
      text: t("visual:empty.session.suggestion_document"),
      onSelect: onSuggestDocument ?? triggerPrefill,
    },
  ].filter((s) => s.text);

  const containerStyle = {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    paddingBottom: "24px",
  };

  const listStyle = {
    display: "flex",
    flexDirection: "column" as const,
    gap: "10px",
    marginTop: "-12px", // overlap slightly with empty shell padding for compact visual rhythm
    width: "100%",
    maxWidth: "360px",
  };

  return (
    <div style={containerStyle}>
      <EmptyShell
        title={t("visual:empty.session.title")}
        hint={t("visual:empty.session.hint")}
        ctaLabel={onCta ? t("visual:empty.session.cta") : undefined}
        onCta={onCta}
      />
      {suggestions.length > 0 && (
        <div style={listStyle}>
          {suggestions.map(({ text, onSelect }, idx) => {
            const isHovered = hoveredIdx === idx;
            const itemStyle = {
              padding: "10px 16px",
              borderRadius: "8px",
              border: `1px solid ${isHovered ? "var(--accent, #6b4f8a)" : "var(--rule-soft, #e8dfcd)"}`,
              background: isHovered ? "rgba(107, 79, 138, 0.05)" : "var(--bg-paper-card, #faf6ef)",
              color: isHovered ? "var(--accent, #6b4f8a)" : "var(--ink-soft, #5b5145)",
              fontFamily: "var(--ff-sans, sans-serif)",
              fontSize: "13px",
              textAlign: "center" as const,
              cursor: "pointer",
              transition: "border-color 0.20s ease, background 0.20s ease, transform 0.20s ease, color 0.20s ease",
              transform: isHovered ? "scale(1.015)" : "scale(1)",
              fontStyle: "italic",
              outline: "none",
            };

            return (
              <button
                key={idx}
                type="button"
                onClick={() => onSelect(text)}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
                style={itemStyle}
              >
                « {text} »
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default EmptySession;
