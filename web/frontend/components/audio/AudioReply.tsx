import { type CSSProperties, type FC, useCallback, useEffect, useRef, useState } from "react";
import { tokens } from "../_shared/armance-tokens";

export interface AudioReplyProps {
  messageId: string;
  text: string;
  ttsUrl: string;
  voiceId?: string;
  autoplay?: boolean;
  /** Accent colour override (defaults to var(--accent)). */
  color?: string;
  t: (key: string) => string;
}

const DB_NAME = "armance-audio-cache";
const STORE = "blobs";

/* ── Tiny IndexedDB wrapper ── */

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB unavailable"));
      return;
    }
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function cacheGet(key: string): Promise<Blob | null> {
  try {
    const db = await openDb();
    return await new Promise<Blob | null>((resolve, reject) => {
      const tx = db.transaction(STORE, "readonly");
      const req = tx.objectStore(STORE).get(key);
      req.onsuccess = () => resolve((req.result as Blob) ?? null);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return null;
  }
}

async function cacheSet(key: string, blob: Blob) {
  try {
    const db = await openDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      tx.objectStore(STORE).put(blob, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    /* ignore */
  }
}

export const AudioReply: FC<AudioReplyProps> = ({
  messageId,
  text,
  ttsUrl,
  voiceId,
  autoplay,
  color,
  t,
}) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  const accent = color || tokens.accent;
  const cacheKey = `${messageId}::${voiceId ?? "default"}`;

  const ensureAudio = useCallback(async (): Promise<HTMLAudioElement> => {
    if (audioRef.current) return audioRef.current;

    let blob = await cacheGet(cacheKey);
    if (!blob) {
      setLoading(true);
      try {
        const res = await fetch(ttsUrl, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ text, voice_id: voiceId, message_id: messageId }),
        });
        if (!res.ok) throw new Error(`TTS failed: ${res.status}`);
        blob = await res.blob();
        await cacheSet(cacheKey, blob);
      } finally {
        setLoading(false);
      }
    }

    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.addEventListener("timeupdate", () => {
      if (audio.duration > 0) setProgress(audio.currentTime / audio.duration);
    });
    audio.addEventListener("ended", () => {
      setPlaying(false);
      setProgress(0);
    });
    audio.addEventListener("pause", () => setPlaying(false));
    audio.addEventListener("play", () => setPlaying(true));
    audioRef.current = audio;
    return audio;
  }, [cacheKey, messageId, text, ttsUrl, voiceId]);

  const toggle = useCallback(async () => {
    setErr(null);
    try {
      const audio = await ensureAudio();
      if (audio.paused) await audio.play();
      else audio.pause();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [ensureAudio]);

  useEffect(() => {
    if (autoplay) toggle();
    return () => {
      audioRef.current?.pause();
      audioRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoplay]);

  /* ── Styles & ring ── */

  const size = 24;
  const radius = size / 2 - 1.5;
  const circumference = 2 * Math.PI * radius;

  const btn: CSSProperties = {
    width: size,
    height: size,
    borderRadius: 999,
    border: "none",
    background: "transparent",
    color: accent,
    cursor: "pointer",
    position: "relative",
    display: "grid",
    placeItems: "center",
    padding: 0,
  };

  return (
    <button
      type="button"
      aria-label={playing ? t("audio:play.pause_aria") : t("audio:play.play_aria")}
      title={err ?? ""}
      onClick={toggle}
      style={btn}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ position: "absolute", inset: 0, transform: "rotate(-90deg)" }}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={tokens.rule}
          strokeWidth="1"
        />
        {playing && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={accent}
            strokeWidth="1.5"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - progress)}
            strokeLinecap="round"
          />
        )}
      </svg>
      {loading ? <DotPulse color={accent} /> : playing ? <PauseIcon /> : <PlayIcon />}
      {err && (
        <span
          aria-hidden="true"
          style={{
            position: "absolute",
            bottom: -16,
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: 9,
            color: "var(--danger, #a44141)",
            fontFamily: tokens.ffMono,
            whiteSpace: "nowrap",
          }}
        >
          {t("audio:play.error")}
        </span>
      )}
    </button>
  );
};

const PlayIcon: FC = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round">
    <path d="M2.5 1.5L8 5l-5.5 3.5z" />
  </svg>
);
const PauseIcon: FC = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
    <rect x="2" y="1.5" width="2.2" height="7" />
    <rect x="5.8" y="1.5" width="2.2" height="7" />
  </svg>
);
const DotPulse: FC<{ color: string }> = ({ color }) => (
  <span
    style={{
      width: 6,
      height: 6,
      borderRadius: 999,
      background: color,
      animation: "armance-pulse 1.2s ease-in-out infinite",
    }}
  />
);

export default AudioReply;
