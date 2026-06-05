import SessionView from "./SessionView";

// Static export: single shell; real ids come from the URL client-side.
export function generateStaticParams() {
  return [{ pid: "_", sid: "_" }];
}
export const dynamicParams = false;

export default function SessionPage() {
  return <SessionView />;
}
