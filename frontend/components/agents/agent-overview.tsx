import { Bot, CircleAlert, CircleCheck, FilePenLine } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

type AgentOverviewProps = {
  total: number;
  active: number;
  needsAttention: number;
  draft: number;
  loading?: boolean;
};

export function AgentOverview({
  total,
  active,
  needsAttention,
  draft,
  loading = false,
}: AgentOverviewProps) {
  const metrics = [
    { label: "Total agents", value: total, icon: Bot },
    { label: "Active", value: active, icon: CircleCheck },
    { label: "Needs attention", value: needsAttention, icon: CircleAlert },
    { label: "Draft or configuring", value: draft, icon: FilePenLine },
  ] as const;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <MetricCard
            key={metric.label}
            label={metric.label}
            value={metric.value}
            description="Derived from the loaded agent list."
            loading={loading}
            headingLevel={3}
            icon={<Icon />}
          />
        );
      })}
    </div>
  );
}
