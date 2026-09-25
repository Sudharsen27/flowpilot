import { CircleAlert, FileText, Library, ScanSearch } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const knowledgeMetrics = [
  {
    label: "Knowledge sources",
    unavailableLabel: "Available when sources connect",
    icon: Library,
  },
  {
    label: "Documents",
    unavailableLabel: "Available when sources connect",
    icon: FileText,
  },
  {
    label: "Indexed",
    unavailableLabel: "Available when sources connect",
    icon: ScanSearch,
  },
  {
    label: "Needs attention",
    unavailableLabel: "Available when sources connect",
    icon: CircleAlert,
  },
] as const;

export function KnowledgeOverview() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {knowledgeMetrics.map((metric) => {
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
