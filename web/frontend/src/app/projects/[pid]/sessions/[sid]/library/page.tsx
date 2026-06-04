import LibraryView from "./LibraryView";

// Static export: single shell; real ids come from the URL client-side.
export function generateStaticParams() {
  return [{ pid: "_", sid: "_" }];
}

export default function LibraryPage() {
  return <LibraryView />;
}

export const dynamicParams = false;
