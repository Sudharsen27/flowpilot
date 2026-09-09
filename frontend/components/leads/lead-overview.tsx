import { CircleCheck, ClockAlert, UserPlus, Users } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const leadMetrics = [
  {
    label: "Total leads",
    unavailableLabel: "No lead data",
    icon: Users,
  },
  {
    label: "New leads",
    unavailableLabel: "No lead data",
    icon: UserPlus,
  },
  {
    label: "Qualified leads",
    unavailableLabel: "Qualification unavailable",
    icon: CircleCheck,
  },
  {
    label: "Follow-up required",
    unavailableLabel: "No follow-up data",
    icon: ClockAlert,
  },
] as const;

export function LeadOverview() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {leadMetrics.map((metric) => {
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
