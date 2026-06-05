import WorkflowView from "./WorkflowView";

// Static export: single shell; real ids come from the URL client-side.
export function generateStaticParams() {
  return [{ pid: "_", sid: "_", name: "_" }];
}

export default function WorkflowPage() {
  return <WorkflowView />;
}

export const dynamicParams = false;
