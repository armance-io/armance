import { type CSSProperties, type FC, useMemo } from "react";
import DOMPurify from "dompurify";
import { tokens } from "../_shared/armance-tokens";

export interface SvgBlockProps {
  source: string;
  t: (key: string) => string;
}

export const SvgBlock: FC<SvgBlockProps> = ({ source, t }) => {
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

  const wrap: CSSProperties = {
    border: `1px solid ${tokens.rule}`,
    background: tokens.bgPaperDeep,
    padding: 16,
    margin: "20px 0",
    overflowX: "auto",
    textAlign: "center",
    borderRadius: 2,
    color: tokens.ink,
  };

  if (!sanitized.ok) {
    return (
      <div style={wrap}>
        <Chip label={t("render:svg.error_title")} />
        <p style={{ margin: "8px 0 0", color: tokens.inkFaint, fontSize: 12, fontStyle: "italic" }}>
          {t("render:svg.error_hint")}
        </p>
      </div>
    );
  }

  return (
    <div
      style={wrap}
      className="armance-svg-block"
      dangerouslySetInnerHTML={{ __html: sanitized.html }}
    />
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
