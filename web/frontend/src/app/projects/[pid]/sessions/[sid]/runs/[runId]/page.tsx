import RunView from "./RunView";

// Static export: single shell; real ids come from the URL client-side.
export function generateStaticParams() {
  return [{ pid: "_", sid: "_", runId: "_" }];
}

export default function RunPage() {
  return <RunView />;
}
