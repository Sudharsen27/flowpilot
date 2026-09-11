import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";

export type ActivityEventStatus =
  "completed" | "pending" | "failed" | "information";

type ActivityStatusBadgeProps = {
  status: ActivityEventStatus;
};

export function ActivityStatusBadge({ status }: ActivityStatusBadgeProps) {
  const presentation =
    status === "information"
      ? statusPresentation("DRAFT", "Information")
      : statusPresentation(status, status.charAt(0).toUpperCase() + status.slice(1));
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}
