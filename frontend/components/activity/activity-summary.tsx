import { Bot, UserRound, Workflow, ListTree } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const activityMetrics = [
  {
    label: "Events",
    unavailableLabel: "No activity data",
    icon: ListTree,
  },
  {
    label: "AI actions",
    unavailableLabel: "No AI activity data",
    icon: Bot,
  },
  {
    label: "Workflow events",
    unavailableLabel: "No workflow activity data",
    icon: Workflow,
  },
  {
    label: "Human actions",
    unavailableLabel: "No human activity data",
    icon: UserRound,
  },
] as const;

export function ActivitySummary() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {activityMetrics.map((metric) => {
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
