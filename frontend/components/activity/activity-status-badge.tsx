import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";

export type ActivityEventStatus =
  "completed" | "pending" | "failed" | "information";

type ActivityStatusBadgeProps = {
  status: ActivityEventStatus;
};

export function humanizeActivityStatus(status: string) {
  return status
    .replace(/[_-]+/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function ActivityStatusBadge({ status }: ActivityStatusBadgeProps) {
  const presentation =
    status === "information"
      ? statusPresentation("DRAFT", "Information")
      : statusPresentation(status, humanizeActivityStatus(status));
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}
