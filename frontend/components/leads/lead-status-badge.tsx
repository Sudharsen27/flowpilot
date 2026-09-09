import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";

export type LeadStatus =
  "new" | "contacted" | "qualified" | "unqualified" | "converted";

type LeadStatusBadgeProps = {
  status: LeadStatus;
};

const statusPresentation: Record<
  LeadStatus,
  { status: StatusValue; label: string }
> = {
  new: { status: "pending", label: "New" },
  contacted: { status: "active", label: "Contacted" },
  qualified: { status: "success", label: "Qualified" },
  unqualified: { status: "draft", label: "Unqualified" },
  converted: { status: "success", label: "Converted" },
};

export function LeadStatusBadge({ status }: LeadStatusBadgeProps) {
  const presentation = statusPresentation[status];
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}
