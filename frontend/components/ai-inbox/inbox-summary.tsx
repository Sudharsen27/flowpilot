import { Bot, Clock3, MessageCircle, UserRoundCheck } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const inboxMetrics = [
  {
    label: "Open conversations",
    unavailableLabel: "No conversation data",
    icon: MessageCircle,
  },
  {
    label: "Waiting for response",
    unavailableLabel: "No response data",
    icon: Clock3,
  },
  {
    label: "AI handled",
    unavailableLabel: "AI handling unavailable",
    icon: Bot,
  },
  {
    label: "Needs human attention",
    unavailableLabel: "No handoff data",
    icon: UserRoundCheck,
  },
] as const;

export function InboxSummary() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {inboxMetrics.map((metric) => {
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
