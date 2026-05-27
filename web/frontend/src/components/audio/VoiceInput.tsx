import { type CSSProperties, type FC, useCallback, useRef, useState } from "react";
import { tokens } from "../_shared/armance-tokens";

export type VoiceState =
  | "idle"
  | "requesting-mic"
  | "recording"
  | "uploading"
  | "error";

export interface VoiceInputProps {
  onTranscript: (text: string) => void;
  onError: (err: Error) => void;
  sttUrl: string;
  disabled?: boolean;
  t: (key: string) => string;
}

export const VoiceInput: FC<VoiceInputProps> = ({
  onTranscript,
  onError,
  sttUrl,
  disabled,
  t,
}) => {
  const [state, setState] = useState<VoiceState>("idle");
  const [errMsg, setErrMsg] = useState<string>("");
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((tr) => tr.stop());
    streamRef.current = null;
  };

  const startRecording = useCallback(async () => {
    if (disabled || state === "recording") return;
    setState("requesting-mic");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = async () => {
        stopStream();
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setState("uploading");
        try {
          const fd = new FormData();
          fd.append("audio", blob, "voice.webm");
          const res = await fetch(sttUrl, { method: "POST", body: fd });
          if (!res.ok) throw new Error(`STT failed: ${res.status}`);
          const data = (await res.json()) as { text?: string };
          onTranscript(data.text ?? "");
          setState("idle");
        } catch (err) {
          const e = err instanceof Error ? err : new Error(String(err));
          setErrMsg(e.message);
          setState("error");
          onError(e);
        }
      };
      recRef.current = rec;
      rec.start();
      setState("recording");
    } catch (err) {
      const e = err instanceof Error ? err : new Error(String(err));
      setErrMsg(e.message);
      setState("error");
      onError(e);
      stopStream();
    }
  }, [disabled, state, sttUrl, onTranscript, onError]);

  const stopRecording = useCallback(() => {
    if (recRef.current && recRef.current.state !== "inactive") {
      recRef.current.stop();
    }
  }, []);

  /* ── Styles ── */

  const isRec = state === "recording";
  const isUp = state === "uploading";
  const isErr = state === "error";

  const btn: CSSProperties = {
    width: 36,
    height: 36,
    borderRadius: 999,
    border: `1px solid ${isErr ? "var(--danger, #a44141)" : isRec ? tokens.accent : tokens.rule}`,
    background: isRec ? tokens.accent : "transparent",
    color: isRec ? tokens.bgPaperCard : tokens.inkSoft,
    display: "grid",
    placeItems: "center",
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "all 160ms ease",
    position: "relative",
    animation: isErr ? "armance-shake 280ms ease" : isRec ? "armance-pulse 1.4s ease-in-out infinite" : undefined,
  };

  return (
    <div style={{ position: "relative", display: "inline-flex", alignItems: "center", gap: 8 }}>
      <button
        type="button"
        aria-label={t("audio:voice.idle_aria")}
        disabled={disabled}
        onMouseDown={startRecording}
        onMouseUp={stopRecording}
        onMouseLeave={() => state === "recording" && stopRecording()}
        onTouchStart={startRecording}
        onTouchEnd={stopRecording}
        title={isErr ? errMsg : ""}
        style={btn}
      >
        {isUp ? <Spinner /> : isRec ? <RecCircle /> : <MicIcon />}
      </button>

      {isRec && <Waveform />}

      {isErr && (
        <span
          role="status"
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            left: 0,
            fontSize: 11,
            color: "var(--danger, #a44141)",
            fontFamily: tokens.ffMono,
            whiteSpace: "nowrap",
          }}
        >
          {t("audio:voice.error")}
        </span>
      )}

      <style>{`
        @keyframes armance-pulse {
          0%,100% { transform: scale(1); }
          50% { transform: scale(1.08); }
        }
        @keyframes armance-shake {
          0%,100% { transform: translateX(0); }
          25% { transform: translateX(-4px); }
          75% { transform: translateX(4px); }
        }
        @keyframes armance-bar {
          0%,100% { transform: scaleY(0.3); }
          50% { transform: scaleY(1); }
        }
        @media (prefers-reduced-motion: reduce) {
          [data-armance-voice] { animation: none !important; }
        }
      `}</style>
    </div>
  );
};

const MicIcon: FC = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
    <rect x="6" y="2" width="4" height="8" rx="2" />
    <path d="M3.5 7.5a4.5 4.5 0 009 0M8 12v2.5M5.5 14.5h5" />
  </svg>
);
const RecCircle: FC = () => (
  <span style={{ width: 10, height: 10, borderRadius: 999, background: "currentColor" }} />
);
const Spinner: FC = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" style={{ animation: "spin 1s linear infinite" }}>
    <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5" fill="none" strokeDasharray="20 40" />
    <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
  </svg>
);
const Waveform: FC = () => (
  <span data-armance-voice style={{ display: "inline-flex", gap: 2, alignItems: "center", height: 18 }}>
    {[0, 1, 2, 3].map((i) => (
      <span
        key={i}
        data-armance-voice
        style={{
          width: 2,
          height: 16,
          background: tokens.accent,
          transformOrigin: "center",
          animation: `armance-bar 800ms ease-in-out ${i * 110}ms infinite`,
        }}
      />
    ))}
  </span>
);

export default VoiceInput;
