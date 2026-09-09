import { CircleAlert, FileText, Library, ScanSearch } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

const knowledgeMetrics = [
  {
    label: "Knowledge sources",
    unavailableLabel: "No source data",
    icon: Library,
  },
  {
    label: "Documents",
    unavailableLabel: "No document data",
    icon: FileText,
  },
  {
    label: "Indexed",
    unavailableLabel: "Indexing unavailable",
    icon: ScanSearch,
  },
  {
    label: "Needs attention",
    unavailableLabel: "No indexing health data",
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
