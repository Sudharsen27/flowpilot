import {
  CalendarCheck,
  MessageSquareText,
  ShieldCheck,
  Users,
} from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const overviewMetrics = [
  {
    label: "Leads",
    unavailableLabel: "Connect a lead source",
    icon: Users,
  },
  {
    label: "Conversations",
    unavailableLabel: "No conversation data",
    icon: MessageSquareText,
  },
  {
    label: "Appointments",
    unavailableLabel: "No appointment data",
    icon: CalendarCheck,
  },
  {
    label: "Pending approvals",
    unavailableLabel: "No approval data",
    icon: ShieldCheck,
  },
] as const;

export function BusinessOverview() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {overviewMetrics.map((metric) => {
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
