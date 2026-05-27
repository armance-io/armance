import {
  type CSSProperties,
  type FC,
  useState,
  useCallback,
  useEffect,
  useRef,
} from "react";

/* ─── Types ──────────────────────────────────────────────────────────────── */

export interface CheckpointDrawerProps {
  kind: "text" | "select" | "confirm";
  prompt: string;
  options?: string[];
  onSubmit: (content: string) => void;
  onAbort: () => void;
  t: (key: string) => string;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const CheckpointDrawer: FC<CheckpointDrawerProps> = ({
  kind,
  prompt,
  options = [],
  onSubmit,
  onAbort,
  t,
}) => {
  const [textValue, setTextValue] = useState("");
  const [selected, setSelected] = useState<string>(options[0] ?? "");
  const [open, setOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  /* Slide in on mount */
  useEffect(() => {
    requestAnimationFrame(() => setOpen(true));
  }, []);

  const handleSubmit = useCallback(() => {
    if (kind === "text") {
      onSubmit(textValue.trim());
    } else if (kind === "select") {
      onSubmit(selected);
    } else {
      onSubmit("yes");
    }
  }, [kind, textValue, selected, onSubmit]);

  const handleNo = useCallback(() => {
    onSubmit("no");
  }, [onSubmit]);

  /* ── Styles ── */

  const overlayStyle: CSSProperties = {
    position: "fixed",
    inset: 0,
    zIndex: 1000,
    display: "flex",
    justifyContent: "flex-end",
  };

  const backdropStyle: CSSProperties = {
    position: "absolute",
    inset: 0,
    background: "rgba(42, 37, 32, 0.2)",
    opacity: open ? 1 : 0,
    transition: "opacity 280ms ease-out",
  };

  const drawerStyle: CSSProperties = {
    position: "relative",
    width: "420px",
    maxWidth: "100vw",
    height: "100%",
    background: "var(--bg-paper, #f4ede0)",
    borderLeft: "1px solid var(--rule, #d6c8ad)",
    display: "flex",
    flexDirection: "column",
    transform: open ? "translateX(0)" : "translateX(100%)",
    transition: "transform 280ms ease-out",
  };

  const headerStyle: CSSProperties = {
    padding: "24px 24px 16px",
    borderBottom: "1px solid var(--rule, #d6c8ad)",
    flexShrink: 0,
  };

  const titleStyle: CSSProperties = {
    fontFamily: "var(--ff-serif, 'Instrument Serif', serif)",
    fontSize: "22px",
    color: "var(--ink, #2a2520)",
    margin: 0,
  };

  const bodyStyle: CSSProperties = {
    flex: 1,
    padding: "24px",
    overflow: "auto",
  };

  const promptStyle: CSSProperties = {
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "16px",
    lineHeight: 1.6,
    color: "var(--ink, #2a2520)",
    margin: "0 0 20px",
    textWrap: "pretty",
  };

  const textareaStyle: CSSProperties = {
    width: "100%",
    minHeight: "120px",
    resize: "vertical",
    border: "1px solid var(--rule, #d6c8ad)",
    borderRadius: "6px",
    padding: "12px 14px",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    lineHeight: 1.6,
    color: "var(--ink, #2a2520)",
    background: "var(--bg-paper-card, #faf6ef)",
    outline: "none",
  };

  const radioListStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  };

  const radioItemStyle = (isSelected: boolean): CSSProperties => ({
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "10px 14px",
    border: `1px solid ${isSelected ? "var(--accent, #6b4f8a)" : "var(--rule, #d6c8ad)"}`,
    borderRadius: "6px",
    cursor: "pointer",
    background: isSelected
      ? "color-mix(in srgb, var(--accent, #6b4f8a) 8%, transparent)"
      : "var(--bg-paper-card, #faf6ef)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    color: "var(--ink, #2a2520)",
    transition: "border-color 120ms ease, background 120ms ease",
  });

  const radioDotStyle = (isSelected: boolean): CSSProperties => ({
    width: "14px",
    height: "14px",
    borderRadius: "999px",
    border: `2px solid ${isSelected ? "var(--accent, #6b4f8a)" : "var(--rule, #d6c8ad)"}`,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  });

  const radioDotInnerStyle: CSSProperties = {
    width: "6px",
    height: "6px",
    borderRadius: "999px",
    background: "var(--accent, #6b4f8a)",
  };

  const footerStyle: CSSProperties = {
    padding: "16px 24px",
    borderTop: "1px solid var(--rule, #d6c8ad)",
    display: "flex",
    gap: "10px",
    justifyContent: "flex-end",
    flexShrink: 0,
    background: "var(--bg-paper-deep, #e8dfcd)",
  };

  const primaryBtnStyle: CSSProperties = {
    padding: "10px 20px",
    borderRadius: "999px",
    border: "none",
    background: "var(--accent, #6b4f8a)",
    color: "var(--bg-paper, #f4ede0)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "background 160ms ease",
  };

  const ghostBtnStyle: CSSProperties = {
    padding: "10px 20px",
    borderRadius: "999px",
    border: "1px solid var(--rule, #d6c8ad)",
    background: "transparent",
    color: "var(--ink, #2a2520)",
    fontFamily: "var(--ff-sans, 'Inter', sans-serif)",
    fontSize: "14px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "border-color 160ms ease, background 160ms ease",
  };

  return (
    <div style={overlayStyle}>
      <style>{`
        @media (prefers-reduced-motion: reduce) {
          * { transition: none !important; }
        }
      `}</style>

      <div style={backdropStyle} onClick={onAbort} aria-hidden="true" />

      <div
        ref={drawerRef}
        style={drawerStyle}
        role="dialog"
        aria-modal="true"
        aria-label={t("checkpoint:drawer.title")}
      >
        <header style={headerStyle}>
          <h2 style={titleStyle}>{t("checkpoint:drawer.title")}</h2>
        </header>

        <div style={bodyStyle}>
          <p style={promptStyle}>{prompt}</p>

          {kind === "text" && (
            <textarea
              style={textareaStyle}
              value={textValue}
              onChange={(e) => setTextValue(e.target.value)}
              autoFocus
            />
          )}

          {kind === "select" && (
            <div style={radioListStyle} role="radiogroup">
              {options.map((opt) => (
                <label
                  key={opt}
                  style={radioItemStyle(selected === opt)}
                  onClick={() => setSelected(opt)}
                >
                  <span style={radioDotStyle(selected === opt)}>
                    {selected === opt && (
                      <span style={radioDotInnerStyle} />
                    )}
                  </span>
                  {opt}
                </label>
              ))}
            </div>
          )}
        </div>

        <footer style={footerStyle}>
          <button style={ghostBtnStyle} onClick={onAbort}>
            {t("checkpoint:drawer.abort")}
          </button>
          {kind === "confirm" ? (
            <>
              <button style={ghostBtnStyle} onClick={handleNo}>
                {t("checkpoint:drawer.no")}
              </button>
              <button style={primaryBtnStyle} onClick={handleSubmit}>
                {t("checkpoint:drawer.yes")}
              </button>
            </>
          ) : (
            <button style={primaryBtnStyle} onClick={handleSubmit}>
              {t("checkpoint:drawer.submit")}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
};

export default CheckpointDrawer;
