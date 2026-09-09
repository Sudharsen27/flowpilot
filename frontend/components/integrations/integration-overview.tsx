import { CircleAlert, Database, Library, PlugZap } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const integrationMetrics = [
  {
    label: "Connected",
    unavailableLabel: "No connection data",
    icon: PlugZap,
  },
  {
    label: "Available",
    unavailableLabel: "Availability not published",
    icon: Library,
  },
  {
    label: "Needs attention",
    unavailableLabel: "No integration health data",
    icon: CircleAlert,
  },
  {
    label: "Data sources",
    unavailableLabel: "No source connection data",
    icon: Database,
  },
] as const;

export function IntegrationOverview() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
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
