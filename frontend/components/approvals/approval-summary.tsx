import { CircleCheck, CircleX, Clock3 } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";
import type { ApprovalQueueStatus } from "@/types/api";

type ApprovalSummaryProps = {
  loading?: boolean;
  activeStatus: ApprovalQueueStatus;
  totals: Partial<Record<ApprovalQueueStatus, number | null>>;
};

const metrics: {
  status: ApprovalQueueStatus;
  label: string;
  description: string;
  unavailableLabel: string;
  icon: typeof Clock3;
}[] = [
  {
    status: "pending",
    label: "Pending review",
    description: "Drafts waiting for a human decision",
    unavailableLabel: "Load pending to see count",
    icon: Clock3,
  },
  {
    status: "approved",
    label: "Approved",
    description: "Approved drafts in this filter",
    unavailableLabel: "Open Approved to load count",
    icon: CircleCheck,
  },
  {
    status: "rejected",
    label: "Rejected",
    description: "Rejected drafts in this filter",
    unavailableLabel: "Open Rejected to load count",
    icon: CircleX,
  },
];

export function ApprovalSummary({
  loading = false,
  activeStatus,
  totals,
}: ApprovalSummaryProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        const value = totals[metric.status];
        const showValue =
          metric.status === activeStatus ||
          (value !== undefined && value !== null);
        return (
          <MetricCard
            key={metric.status}
            label={metric.label}
            value={showValue && value !== undefined && value !== null ? value : undefined}
            description={metric.description}
            unavailableLabel={metric.unavailableLabel}
            headingLevel={3}
            loading={loading && metric.status === activeStatus}
            icon={<Icon />}
          />
        );
      })}
    </div>
  );
}
