"use client";

import LibraryPaneContainer from "@/components/library/LibraryPaneContainer";
import { useRouteParams } from "@/lib/routeParams";

export default function LibraryView() {
  const { pid, sid } = useRouteParams();
  return <LibraryPaneContainer pid={pid} sid={sid} />;
}
