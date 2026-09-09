import { CircleAlert, CircleCheck, FilePenLine, Workflow } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const workflowMetrics = [
  {
    label: "Total workflows",
    unavailableLabel: "No workflow data",
    icon: Workflow,
  },
  {
    label: "Active",
    unavailableLabel: "No active workflows",
    icon: CircleCheck,
  },
  {
    label: "Draft",
    unavailableLabel: "No workflow drafts",
    icon: FilePenLine,
  },
  {
    label: "Needs attention",
    unavailableLabel: "No workflow health data",
    icon: CircleAlert,
  },
] as const;

export function WorkflowOverview() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {workflowMetrics.map((metric) => {
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
