import {
  type CSSProperties,
  type FC,
  useState,
  useCallback,
} from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface DepthPickerProps {
  workflowName: string;
  onLaunch: (
    mode: "interactive" | "autonomous",
    depth: "quick" | "deep",
  ) => void;
  t: (key: string) => string;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const DepthPicker: FC<DepthPickerProps> = ({
  workflowName,
  onLaunch,
  t,
}) => {
  const [depth, setDepth] = useState<"quick" | "deep">("quick");
  const [mode, setMode] = useState<"interactive" | "autonomous">(
    "interactive",
  );

  const handleLaunch = useCallback(() => {
    onLaunch(mode, depth);
  }, [mode, depth, onLaunch]);

  /* ── Styles ── */

  const rootStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "28px",
    padding: "32px 24px",
  };

  const titleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "22px",
    color: "var(--ink, #2a2520)",
    margin: 0,
    textAlign: "center",
  };

  const cardsRowStyle: CSSProperties = {
    display: "flex",
    gap: "16px",
    flexWrap: "wrap",
    justifyContent: "center",
  };

  const cardStyle = (isSelected: boolean): CSSProperties => ({
    width: "280px",
    minHeight: "180px",
    border: `${isSelected ? "2px" : "1px"} solid ${isSelected ? "var(--accent, #6b4f8a)" : "var(--rule, #d6c8ad)"}`,
    padding: "20px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    cursor: "pointer",
    background: "var(--bg-paper-card, #faf6ef)",
    transition: "border-color 160ms ease, box-shadow 160ms ease",
  });

  const cardTitleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "20px",
    color: "var(--ink, #2a2520)",
    margin: 0,
  };

  const cardDescStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    lineHeight: 1.55,
    color: "var(--ink-soft, #5b5145)",
    margin: 0,
    flex: 1,
  };

  const toggleWrapStyle: CSSProperties = {
    display: "flex",
    border: "1px solid var(--rule, #d6c8ad)",
    borderRadius: "999px",
    overflow: "hidden",
  };

  const toggleBtnStyle = (active: boolean): CSSProperties => ({
    padding: "8px 16px",
    border: "none",
    background: active
      ? "var(--accent, #6b4f8a)"
      : "transparent",
    color: active
      ? "var(--bg-paper, #f4ede0)"
      : "var(--ink-soft, #5b5145)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "13px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "background 160ms ease, color 160ms ease",
  });

  const hintStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontStyle: "italic",
    fontSize: "13px",
    color: "var(--ink-faint, #9c8e7e)",
    maxWidth: "36ch",
    textAlign: "center",
    lineHeight: 1.45,
  };

  const launchBtnStyle: CSSProperties = {
    padding: "14px 32px",
    borderRadius: "999px",
    border: "none",
    background: "var(--accent, #6b4f8a)",
    color: "var(--bg-paper, #f4ede0)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "15px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "background 160ms ease",
  };

  return (
    <div style={rootStyle}>
      <style>{`
        @media (prefers-reduced-motion: reduce) {
          * { transition: none !important; }
        }
      `}</style>

      <h3 style={titleStyle}>{workflowName}</h3>

      {/* Depth cards */}
      <div style={cardsRowStyle}>
        <div
          style={cardStyle(depth === "quick")}
          onClick={() => setDepth("quick")}
          role="radio"
          aria-checked={depth === "quick"}
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") setDepth("quick");
          }}
          onMouseEnter={(e) => {
            if (depth !== "quick")
              e.currentTarget.style.borderColor =
                "var(--accent-soft, #b7a4c9)";
          }}
          onMouseLeave={(e) => {
            if (depth !== "quick")
              e.currentTarget.style.borderColor =
                "var(--rule, #d6c8ad)";
          }}
        >
          <div style={{
            width: "12px",
            height: "12px",
            borderRadius: "50%",
            background: "hsl(120, 15%, 55%)",
            border: "1px solid hsl(120, 15%, 45%)",
            display: "inline-block",
            flexShrink: 0,
          }} />
          <h4 style={cardTitleStyle}>
            {t("workflow:picker.quick_title")}
          </h4>
          <p style={cardDescStyle}>
            {t("workflow:picker.quick_desc")}
          </p>
        </div>

        <div
          style={cardStyle(depth === "deep")}
          onClick={() => setDepth("deep")}
          role="radio"
          aria-checked={depth === "deep"}
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") setDepth("deep");
          }}
          onMouseEnter={(e) => {
            if (depth !== "deep")
              e.currentTarget.style.borderColor =
                "var(--accent-soft, #b7a4c9)";
          }}
          onMouseLeave={(e) => {
            if (depth !== "deep")
              e.currentTarget.style.borderColor =
                "var(--rule, #d6c8ad)";
          }}
        >
          <div style={{
            width: "12px",
            height: "12px",
            borderRadius: "50%",
            background: "hsl(0, 30%, 65%)",
            border: "1px solid hsl(0, 30%, 55%)",
            display: "inline-block",
            flexShrink: 0,
          }} />
          <h4 style={cardTitleStyle}>
            {t("workflow:picker.deep_title")}
          </h4>
          <p style={cardDescStyle}>
            {t("workflow:picker.deep_desc")}
          </p>
        </div>
      </div>

      {/* Mode toggle */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <div style={toggleWrapStyle} role="radiogroup">
          <button
            style={toggleBtnStyle(mode === "interactive")}
            onClick={() => setMode("interactive")}
            role="radio"
            aria-checked={mode === "interactive"}
          >
            {t("workflow:picker.mode_interactive")}
          </button>
          <button
            style={toggleBtnStyle(mode === "autonomous")}
            onClick={() => setMode("autonomous")}
            role="radio"
            aria-checked={mode === "autonomous"}
          >
            {t("workflow:picker.mode_autonomous")}
          </button>
        </div>
        <div style={hintStyle}>
          {mode === "interactive"
            ? t("workflow:picker.hint_interactive")
            : t("workflow:picker.hint_autonomous")}
        </div>
      </div>

      {/* Launch */}
      <button
        style={launchBtnStyle}
        onClick={handleLaunch}
        onMouseEnter={(e) => {
          e.currentTarget.style.background =
            "var(--accent-deep, #4a3666)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background =
            "var(--accent, #6b4f8a)";
        }}
      >
        {t("workflow:picker.launch")}
      </button>
    </div>
  );
};

export default DepthPicker;
