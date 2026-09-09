import { cn } from "@/lib/utils";

export type StatusValue =
  | "active"
  | "draft"
  | "paused"
  | "success"
  | "pending"
  | "failed"
  | "warning"
  | "high"
  | "medium"
  | "low";

type StatusBadgeProps = {
  status: StatusValue;
  label?: string;
  className?: string;
};

const labels: Record<StatusValue, string> = {
  active: "Active",
  draft: "Draft",
  paused: "Paused",
  success: "Success",
  pending: "Pending",
  failed: "Failed",
  warning: "Warning",
  high: "High",
  medium: "Medium",
  low: "Low",
};

const appearances: Record<StatusValue, string> = {
  active: "border-success/25 bg-success/10 text-success-text",
  success: "border-success/25 bg-success/10 text-success-text",
  draft: "border-border bg-muted text-muted-foreground",
  paused: "border-warning/30 bg-warning/10 text-warning-text",
  pending: "border-info/25 bg-info/10 text-info-text",
  failed: "border-destructive/25 bg-destructive/10 text-danger-text",
  warning: "border-warning/30 bg-warning/10 text-warning-text",
  high: "border-destructive/25 bg-destructive/10 text-danger-text",
  medium: "border-warning/30 bg-warning/10 text-warning-text",
  low: "border-info/25 bg-info/10 text-info-text",
};

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  return (
    <span
      data-slot="status-badge"
      data-status={status}
      className={cn(
        "inline-flex min-h-6 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium",
        appearances[status],
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {label ?? labels[status]}
    </span>
  );
}
