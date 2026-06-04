import { type CSSProperties, type FC, useMemo, useState } from "react";
import DOMPurify from "dompurify";
import { tokens } from "../_shared/armance-tokens";

export interface SvgBlockProps {
  source: string;
  t: (key: string) => string;
}

export const SvgBlock: FC<SvgBlockProps> = ({ source, t }) => {
  const [copied, setCopied] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  const sanitized = useMemo(() => {
    try {
      const clean = DOMPurify.sanitize(source, {
        USE_PROFILES: { svg: true, svgFilters: true },
        FORBID_TAGS: ["script", "iframe", "embed", "object", "foreignObject"],
        FORBID_ATTR: [
          "onload", "onerror", "onclick", "onmouseover", "onmouseout",
          "onfocus", "onblur", "onchange", "onsubmit", "onkeydown",
          "onkeyup", "onkeypress",
        ],
        ALLOWED_URI_REGEXP: /^(?:https?:|data:image\/|#)/i,
      });
      return { ok: true as const, html: clean };
    } catch (e) {
      return { ok: false as const, error: e instanceof Error ? e.message : String(e) };
    }
  }, [source]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(source);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* noop */
    }
  };

  const handleDownload = () => {
    try {
      const blob = new Blob([source], { type: "image/svg+xml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "render.svg";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setDownloaded(true);
      setTimeout(() => setDownloaded(false), 1500);
    } catch {
      /* noop */
    }
  };

  const container: CSSProperties = {
    border: `1px solid ${tokens.rule}`,
    background: tokens.bgPaperDeep,
    borderRadius: 2,
    margin: "20px 0",
    overflow: "hidden",
  };

  const header: CSSProperties = {
    height: 28,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 10px",
    borderBottom: `1px solid ${tokens.rule}`,
    background: tokens.bgPaperCard,
  };

  const pill: CSSProperties = {
    fontFamily: tokens.ffMono,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: tokens.inkSoft,
  };

  const actions: CSSProperties = {
    display: "flex",
    gap: 6,
  };

  const btnStyle: CSSProperties = {
    border: `1px solid ${tokens.rule}`,
    background: "transparent",
    color: tokens.inkSoft,
    fontFamily: tokens.ffMono,
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    padding: "2px 8px",
    cursor: "pointer",
    borderRadius: 2,
  };

  const wrap: CSSProperties = {
    background: tokens.bgPaperDeep,
    padding: 16,
    overflowX: "auto",
    textAlign: "center",
    color: tokens.ink,
  };

  if (!sanitized.ok) {
    return (
      <div style={{ ...wrap, border: `1px solid ${tokens.rule}`, borderRadius: 2 }}>
        <Chip label={t("render:svg.error_title")} />
        <p style={{ margin: "8px 0 0", color: tokens.inkFaint, fontSize: 12, fontStyle: "italic" }}>
          {t("render:svg.error_hint")}
        </p>
      </div>
    );
  }

  return (
    <div style={container} className="armance-svg-block">
      <div style={header}>
        <span style={pill}>SVG</span>
        <div style={actions}>
          <button type="button" style={btnStyle} onClick={handleCopy}>
            {copied ? t("render:code.copied") : t("render:code.copy")}
          </button>
          <button type="button" style={btnStyle} onClick={handleDownload}>
            {downloaded ? t("render:code.downloaded") : t("render:code.download")}
          </button>
        </div>
      </div>
      <div
        style={wrap}
        dangerouslySetInnerHTML={{ __html: sanitized.html }}
      />
    </div>
  );
};

const Chip: FC<{ label: string }> = ({ label }) => (
  <span
    style={{
      display: "inline-block",
      padding: "3px 10px",
      borderRadius: 999,
      border: `1px solid ${tokens.accentSoft}`,
      background: tokens.bgPaperCard,
      color: tokens.accentDeep,
      fontFamily: tokens.ffMono,
      fontSize: 11,
      textTransform: "uppercase",
      letterSpacing: "0.08em",
    }}
  >
    {label}
  </span>
);

export default SvgBlock;
