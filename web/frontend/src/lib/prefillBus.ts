type PrefillListener = (text: string) => void;
const listeners = new Set<PrefillListener>();

export function onPrefill(cb: PrefillListener): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function triggerPrefill(text: string) {
  for (const cb of listeners) {
    cb(text);
  }
}
