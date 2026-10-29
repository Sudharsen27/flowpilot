import Link from "next/link";

import { BarListChart, ColumnChart, magnitudeOf } from "@/components/charts/bar-charts";
import { ChartCard } from "@/components/charts/chart-card";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DEAL_STAGE_LABELS, isClosedStage } from "@/lib/deals";
import { formatMoney, formatMoneyCompact, formatMonth } from "@/lib/money";
import type { PipelineSummary } from "@/types/api";

type ChartsProps = {
  /** undefined while loading, null when unavailable. */
  summary: PipelineSummary | null | undefined;
  onRetry: () => void;
};

function Unavailable({ onRetry }: { onRetry: () => void }) {
  return (
    <StatePanel
      kind="error"
      className="max-w-none border-0 p-0 shadow-none"
      headingLevel={3}
      title="Pipeline figures could not be loaded"
      description="Other dashboard sections are unaffected."
      action={
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      }
    />
  );
}

export function PipelineByStageChart({ summary, onRetry }: ChartsProps) {
  const open = summary?.by_stage.filter((row) => !isClosedStage(row.stage)) ?? [];
  return (
    <ChartCard
      title="Open pipeline by stage"
      description="Total value of open deals in each stage"
      figure={
        summary ? (
          <p className="text-metric font-semibold tracking-tight tabular-nums">
            {formatMoney(summary.open.total_amount, summary.currency)}
          </p>
        ) : null
      }
      action={
        <Link href="/deals/pipeline" className={buttonVariants({ variant: "outline", size: "sm" })}>
          View board
        </Link>
      }
    >
      {summary === undefined ? (
        <div className="grid gap-2.5" role="status">
          {[0, 1, 2, 3].map((index) => (
            <Skeleton key={index} className="h-5" />
          ))}
          <span className="sr-only">Loading pipeline by stage</span>
        </div>
      ) : summary === null ? (
        <Unavailable onRetry={onRetry} />
      ) : (
        <BarListChart
          valueLabel="Open value"
          categoryLabel="Stage"
          emptyMessage="No open deals yet. Create a deal to start your pipeline."
          data={open.map((row) => ({
            key: row.stage,
            label: DEAL_STAGE_LABELS[row.stage],
            value: formatMoneyCompact(row.total_amount, summary.currency),
            magnitude: magnitudeOf(row.total_amount),
            details: [
              formatMoney(row.total_amount, summary.currency),
              `${row.count} ${row.count === 1 ? "deal" : "deals"}`,
              `Weighted ${formatMoney(row.weighted_amount, summary.currency)}`,
            ],
          }))}
        />
      )}
    </ChartCard>
  );
}

export function WonRevenueChart({ summary, onRetry }: ChartsProps) {
  const total = summary?.won_by_month.length ?? 6;
  return (
    <ChartCard
      title="Won revenue"
      description={`Deals closed as won, by month (last ${total} months)`}
      figure={
        summary ? (
          <p className="text-metric font-semibold tracking-tight tabular-nums">
            {formatMoney(summary.won.total_amount, summary.currency)}
            <span className="text-muted-foreground ml-2 text-xs font-normal">all time</span>
          </p>
        ) : null
      }
    >
      {summary === undefined ? (
        <Skeleton className="h-44" />
      ) : summary === null ? (
        <Unavailable onRetry={onRetry} />
      ) : (
        <ColumnChart
          valueLabel="Won revenue"
          categoryLabel="Month"
          emptyMessage="No deals have been won in this period."
          data={summary.won_by_month.map((row) => ({
            key: row.month,
            label: formatMonth(row.month).split(" ")[0]?.slice(0, 3) ?? row.month,
            value: formatMoneyCompact(row.total_amount, summary.currency),
            magnitude: magnitudeOf(row.total_amount),
            details: [
              formatMonth(row.month),
              formatMoney(row.total_amount, summary.currency),
              `${row.count} ${row.count === 1 ? "deal" : "deals"} won`,
            ],
          }))}
        />
      )}
    </ChartCard>
  );
}
