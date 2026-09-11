import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";
import type { SalesRunStatus } from "@/types/api";

const labels: Record<SalesRunStatus, string> = {
  RUNNING: "Processing",
  WAITING_APPROVAL: "Waiting for approval",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

export function SalesRunStatusBadge({ status }: { status: SalesRunStatus }) {
  const presentation = statusPresentation(status, labels[status]);
  return <StatusBadge status={presentation.status} label={presentation.label} />;
}
