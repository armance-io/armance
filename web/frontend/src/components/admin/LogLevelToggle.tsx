import { type CSSProperties, type FC, useState } from "react";
import { tokens } from "../_shared/armance-tokens";

type Level = "INFO" | "DEBUG" | "WARN" | "ERROR";

export interface LogLevelToggleProps {
  current: Level;
  onChange: (level: Level) => Promise<void>;
  t: (key: string) => string;
}

const LEVELS: Level[] = ["DEBUG", "INFO", "WARN", "ERROR"];

export const LogLevelToggle: FC<LogLevelToggleProps> = ({ current, onChange, t }) => {
  const [active, setActive] = useState<Level>(current);
  const [saving, setSaving] = useState(false);

  const wrap: CSSProperties = {
    display: "flex",
    gap: 8,
    alignItems: "center",
    fontFamily: tokens.ffMono,
    fontSize: 13,
  };

  const label: CSSProperties = { color: tokens.inkSoft, marginRight: 8 };

  return (
    <div style={wrap}>
      <span style={label}>{t("admin:logs.level")}</span>
      {LEVELS.map((lvl) => (
        <button
          key={lvl}
          disabled={saving}
          onClick={async () => {
            setSaving(true);
            try {
              await onChange(lvl);
              setActive(lvl);
            } finally {
              setSaving(false);
            }
          }}
          style={{
            padding: "4px 12px",
            border: `1px solid ${active === lvl ? tokens.accent : tokens.rule}`,
            background: active === lvl ? tokens.accent : "transparent",
            color: active === lvl ? "#fff" : tokens.ink,
            cursor: saving ? "not-allowed" : "pointer",
            fontFamily: tokens.ffMono,
            fontSize: 12,
          }}
        >
          {lvl}
        </button>
      ))}
    </div>
  );
};

export default LogLevelToggle;
