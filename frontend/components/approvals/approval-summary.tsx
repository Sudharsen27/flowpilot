import { CircleCheck, CircleX, Clock3, ShieldAlert } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const approvalMetrics = [
  {
    label: "Pending",
    unavailableLabel: "No approval data",
    icon: Clock3,
  },
  {
    label: "Approved",
    unavailableLabel: "No approval history",
    icon: CircleCheck,
  },
  {
    label: "Rejected",
    unavailableLabel: "No approval history",
    icon: CircleX,
  },
  {
    label: "High-risk actions",
    unavailableLabel: "No risk data",
    icon: ShieldAlert,
  },
] as const;

export function ApprovalSummary() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {approvalMetrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <MetricCard
            key={metric.label}
            label={metric.label}
            unavailableLabel={metric.unavailableLabel}
            headingLevel={3}
            icon={<Icon />}
          />
        );
      })}
    </div>
  );
}
