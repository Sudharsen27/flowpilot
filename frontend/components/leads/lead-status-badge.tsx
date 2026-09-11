import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";
import type { LeadStatus } from "@/types/api";

type LeadStatusBadgeProps = {
  status: LeadStatus;
};

const leadPresentation: Record<
  LeadStatus,
  { code: string; label: string; fallback?: "active" | "draft" | "success" }
> = {
  NEW: { code: "NEW", label: "New" },
  CONTACTED: { code: "CONTACTED", label: "Contacted", fallback: "active" },
  QUALIFIED: { code: "QUALIFIED", label: "Qualified" },
  UNQUALIFIED: { code: "UNQUALIFIED", label: "Unqualified", fallback: "draft" },
  CONVERTED: { code: "CONVERTED", label: "Converted", fallback: "success" },
};

export function LeadStatusBadge({ status }: LeadStatusBadgeProps) {
  const item = leadPresentation[status];
  const presentation = statusPresentation(
    item.code,
    item.label,
    item.fallback ?? "draft",
  );
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}
