import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import type { LeadStatus } from "@/types/api";

type LeadStatusBadgeProps = {
  status: LeadStatus;
};

const statusPresentation: Record<
  LeadStatus,
  { status: StatusValue; label: string }
> = {
  NEW: { status: "pending", label: "New" },
  CONTACTED: { status: "active", label: "Contacted" },
  QUALIFIED: { status: "success", label: "Qualified" },
  UNQUALIFIED: { status: "draft", label: "Unqualified" },
  CONVERTED: { status: "success", label: "Converted" },
};

export function LeadStatusBadge({ status }: LeadStatusBadgeProps) {
  const presentation = statusPresentation[status];
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}
