import AdminView from "./AdminView";

// Static export: emit a single shell. Real ids are read client-side from
// the URL (see useRouteParams), so the sentinel value is never user-visible.
export function generateStaticParams() {
  return [{ pid: "_" }];
}

export default function AdminPage() {
  return <AdminView />;
}

export const dynamicParams = false;
