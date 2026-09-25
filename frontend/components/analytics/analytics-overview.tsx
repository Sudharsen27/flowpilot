import {
  Bot,
  CalendarCheck,
  MessageSquareText,
  UserRoundCheck,
  Users,
  UserCheck,
} from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const overviewMetrics = [
  {
    label: "Leads generated",
    unavailableLabel: "Unavailable until analytics data is connected",
    icon: Users,
  },
  {
    label: "Qualified leads",
    unavailableLabel: "Unavailable until analytics data is connected",
    icon: UserCheck,
  },
  {
    label: "Conversations",
    unavailableLabel: "Unavailable until analytics data is connected",
    icon: MessageSquareText,
  },
  {
    label: "Appointments",
    unavailableLabel: "Unavailable until analytics data is connected",
    icon: CalendarCheck,
  },
  {
    label: "AI handled",
    unavailableLabel: "Unavailable until analytics data is connected",
    icon: Bot,
  },
  {
    label: "Human handoffs",
    unavailableLabel: "Unavailable until analytics data is connected",
    icon: UserRoundCheck,
  },
] as const;

export function AnalyticsOverview() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
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
