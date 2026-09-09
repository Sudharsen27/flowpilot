import { Bot, CircleAlert, CircleCheck, FilePenLine } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const agentMetrics = [
  {
    label: "Total agents",
    unavailableLabel: "No agent data",
    icon: Bot,
  },
  {
    label: "Active",
    unavailableLabel: "No active agents",
    icon: CircleCheck,
  },
  {
    label: "Needs attention",
    unavailableLabel: "No agent health data",
    icon: CircleAlert,
  },
  {
    label: "Draft or configuring",
    unavailableLabel: "No agent configurations",
    icon: FilePenLine,
  },
] as const;

export function AgentOverview() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {agentMetrics.map((metric) => {
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
