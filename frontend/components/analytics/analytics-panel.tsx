import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export type AnalyticsPanelRow = {
  label: string;
  value: string;
  hint?: string;
};

type AnalyticsPanelProps = {
  title: string;
  description: string;
  headingId: string;
  rows: readonly AnalyticsPanelRow[];
  loading?: boolean;
  emptyMessage?: string;
};

export function AnalyticsPanel({
  title,
  description,
  headingId,
  rows,
  loading = false,
  emptyMessage = "Nothing recorded in this period.",
}: AnalyticsPanelProps) {
  return (
    <Card
      as="section"
      aria-labelledby={headingId}
      aria-describedby={`${headingId}-description`}
      aria-busy={loading || undefined}
      className="h-full"
    >
      <CardContent className="flex h-full flex-col gap-4">
        <div>
          <h3 id={headingId} className="text-base font-medium tracking-tight">
            {title}
          </h3>
          <p
            id={`${headingId}-description`}
            className="text-muted-foreground mt-1 text-sm leading-6"
          >
            {description}
          </p>
        </div>

        {loading ? (
          <div className="grid gap-2" role="status">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <span className="sr-only">Loading {title}</span>
          </div>
        ) : rows.length === 0 ? (
          <p className="text-muted-foreground border-border rounded-md border border-dashed px-3 py-6 text-center text-sm">
            {emptyMessage}
          </p>
        ) : (
          <dl className="grid gap-2">
            {rows.map((row) => (
              <div
                key={row.label}
                className="border-border bg-surface-subtle flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm"
              >
                <dt className="min-w-0">
                  <span className="block">{row.label}</span>
                  {row.hint ? (
                    <span className="text-muted-foreground block text-xs">{row.hint}</span>
                  ) : null}
                </dt>
                <dd className="font-medium tabular-nums">{row.value}</dd>
              </div>
            ))}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}

export function AnalyticsPanelGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-4 xl:grid-cols-2">{children}</div>;
}
