import ProjectEntryView from "./ProjectEntryView";

// Static export: emit a single shell. The real pid is read client-side from
// the URL (see useRouteParams), so the sentinel value is never user-visible.
export function generateStaticParams() {
  return [{ pid: "_" }];
}

export default function ProjectEntryPage() {
  return <ProjectEntryView />;
}

export const dynamicParams = false;
