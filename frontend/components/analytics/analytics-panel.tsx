import { ChartColumn } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

type AnalyticsPanelProps = {
  title: string;
  description: string;
  metrics: readonly string[];
  headingId: string;
};

export function AnalyticsPanel({
  title,
  description,
  metrics,
  headingId,
}: AnalyticsPanelProps) {
  return (
    <Card as="section" aria-labelledby={headingId} className="h-full">
      <CardContent className="flex h-full flex-col gap-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 id={headingId} className="text-base font-medium tracking-tight">
              {title}
            </h3>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              {description}
            </p>
          </div>
          <StatusBadge status="draft" label="Data unavailable" />
        </div>

        <div
          className="border-border bg-surface-subtle flex min-h-44 flex-col items-center justify-center rounded-lg border border-dashed px-4 py-8 text-center"
          role="img"
          aria-label={`${title} chart placeholder. Data will appear here.`}
        >
          <ChartColumn
            className="text-muted-foreground size-5"
            aria-hidden="true"
          />
          <p className="mt-3 text-sm font-medium">Data will appear here</p>
          <p className="text-muted-foreground mt-1 max-w-sm text-xs leading-5">
            This area is a placeholder. No chart series, percentages, or trends
            are displayed.
          </p>
        </div>

        <ul
          className="grid gap-2 sm:grid-cols-2"
          aria-label={`${title} metric concepts`}
        >
          {metrics.map((metric) => (
            <li
              key={metric}
              className="border-border bg-surface-subtle flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm"
            >
              <span>{metric}</span>
              <span className="text-muted-foreground text-xs">Unavailable</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export function AnalyticsPanelGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-4 xl:grid-cols-2">{children}</div>;
}
