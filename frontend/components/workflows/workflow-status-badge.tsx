import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";

export type WorkflowStatus = "draft" | "active" | "paused" | "needs-attention";

type WorkflowStatusBadgeProps = {
  status: WorkflowStatus;
};

const statusPresentation: Record<
  WorkflowStatus,
  { status: StatusValue; label: string }
> = {
  draft: { status: "draft", label: "Draft" },
  active: { status: "active", label: "Active" },
  paused: { status: "paused", label: "Paused" },
  "needs-attention": { status: "warning", label: "Needs attention" },
};

export function WorkflowStatusBadge({ status }: WorkflowStatusBadgeProps) {
  const presentation = statusPresentation[status];
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}
