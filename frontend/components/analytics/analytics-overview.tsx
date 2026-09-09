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
    unavailableLabel: "No lead data",
    icon: Users,
  },
  {
    label: "Qualified leads",
    unavailableLabel: "Qualification unavailable",
    icon: UserCheck,
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
    label: "AI handled",
    unavailableLabel: "AI handling unavailable",
    icon: Bot,
  },
  {
    label: "Human handoffs",
    unavailableLabel: "No handoff data",
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
