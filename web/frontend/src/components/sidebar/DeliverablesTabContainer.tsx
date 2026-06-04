"use client";

import { type FC } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import { DeliverablesTab, type DeliverableRow } from "./DeliverablesTab";

export interface DeliverablesTabContainerProps {
  pid: string;
  sid: string;
  onOpen: (id: string) => void;
}

export const DeliverablesTabContainer: FC<DeliverablesTabContainerProps> = ({
  pid,
  sid,
  onOpen,
}) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: deliverables = [] } = useQuery<DeliverableRow[]>({
    queryKey: ["deliverables", pid, sid],
    queryFn: () => api.get<DeliverableRow[]>(`/projects/${pid}/sessions/${sid}/deliverables`),
  });

  const starMutation = useMutation({
    mutationFn: ({ id, starred }: { id: string; starred: boolean }) =>
      api.patch<DeliverableRow>(`/projects/${pid}/sessions/${sid}/deliverables/${id}/star`, {
        starred,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["deliverables", pid, sid] });
    },
  });

  const onStar = (id: string, starred: boolean) => {
    starMutation.mutate({ id, starred });
  };

  return (
    <DeliverablesTab
      deliverables={deliverables}
      onOpen={onOpen}
      onStar={onStar}
      t={t}
    />
  );
};

export default DeliverablesTabContainer;
