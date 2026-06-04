import RunDetailView from "./RunDetailView";

// Static export: single shell; real ids come from the URL client-side.
export function generateStaticParams() {
  return [{ pid: "_", sid: "_", name: "_", runId: "_" }];
}

export default function RunDetailPage() {
  return <RunDetailView />;
}

export const dynamicParams = true;
