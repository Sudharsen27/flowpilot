import { CircleAlert, Database, Library, PlugZap } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const integrationMetrics = [
  {
    label: "Connected",
    unavailableLabel: "Available when connections exist",
    icon: PlugZap,
  },
  {
    label: "Available",
    unavailableLabel: "Available when integrations launch",
    icon: Library,
  },
  {
    label: "Needs attention",
    unavailableLabel: "Available when connections exist",
    icon: CircleAlert,
  },
  {
    label: "Data sources",
    unavailableLabel: "Available when connections exist",
    icon: Database,
  },
] as const;

export function IntegrationOverview() {
  return (
    <div className="grid max-w-5xl gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {integrationMetrics.map((metric) => {
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
