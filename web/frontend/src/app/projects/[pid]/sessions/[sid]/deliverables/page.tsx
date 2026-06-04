import DeliverablesView from "./DeliverablesView";

// Static export: single shell; real ids come from the URL client-side.
export function generateStaticParams() {
  return [{ pid: "_", sid: "_" }];
}

export default function DeliverablesPage() {
  return <DeliverablesView />;
}

export const dynamicParams = false;
