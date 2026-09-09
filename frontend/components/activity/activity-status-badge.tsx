import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";

export type ActivityEventStatus =
  "completed" | "pending" | "failed" | "information";

type ActivityStatusBadgeProps = {
  status: ActivityEventStatus;
};

const statusPresentation: Record<
  ActivityEventStatus,
  { status: StatusValue; label: string }
> = {
  completed: { status: "success", label: "Completed" },
  pending: { status: "pending", label: "Pending" },
  failed: { status: "failed", label: "Failed" },
  information: { status: "draft", label: "Information" },
};

export function ActivityStatusBadge({ status }: ActivityStatusBadgeProps) {
  const presentation = statusPresentation[status];
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}
