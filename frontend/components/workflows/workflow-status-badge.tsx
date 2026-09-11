import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";

export type WorkflowStatus = "draft" | "active" | "paused" | "needs-attention";

type WorkflowStatusBadgeProps = {
  status: WorkflowStatus;
};

const statusLabels: Record<WorkflowStatus, string> = {
  draft: "Draft",
  active: "Active",
  paused: "Paused",
  "needs-attention": "Needs attention",
};

export function WorkflowStatusBadge({ status }: WorkflowStatusBadgeProps) {
  const presentation = statusPresentation(status, statusLabels[status]);
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}
