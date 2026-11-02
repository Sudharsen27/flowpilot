import type { ReactNode } from "react";

import { GroupedColumnChart, magnitudeOf, type ColumnSeries } from "@/components/charts/bar-charts";
import { ChartCard } from "@/components/charts/chart-card";
import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { SectionHeader } from "@/components/layout/section-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatAbsoluteTimestamp } from "@/lib/datetime";
import { dealCount, formatForecastPeriodShort } from "@/lib/forecast";
import {
  accuracyBasisLabel,
  accuracyLeadLabel,
  comparisonOf,
  formatAccuracyPercent,
  formatSignedMoney,
  formatSignedPercent,
  leadOf,
  snapshotStatusShortText,
  snapshotStatusText,
} from "@/lib/forecast-accuracy";
import { formatMoney, formatMoneyCompact, formatMonth } from "@/lib/money";
import type { ForecastAccuracy, ForecastAccuracyBasis, ForecastAccuracyMonth } from "@/types/api";

type MonthsProps = {
  accuracy: ForecastAccuracy;
  lead: number;
  basis: ForecastAccuracyBasis;
};

/** Solid for what happened; outlined and tinted for the estimate, as on the forecast page. */
const SERIES: ColumnSeries[] = [
  { key: "actual", label: "Won revenue (actual)", markClassName: "bg-chart-1" },
  {
    key: "forecast",
    label: "Saved forecast (estimate)",
    markClassName: "bg-chart-2/40 border border-dashed border-chart-2",
  },
];

function monthName(month: ForecastAccuracyMonth): string {
  const name = formatMonth(month.period_start);
  return month.status === "IN_PROGRESS" ? `${name} (in progress)` : name;
}

export function ForecastAccuracyChart({ accuracy, lead, basis }: MonthsProps) {
  const { currency } = accuracy;
  return (
    <ChartCard
      title="Forecast vs actual by month"
      description={`Revenue won in each month against the ${accuracyBasisLabel(basis).toLowerCase()} forecast saved at ${accuracyLeadLabel(lead).toLowerCase()}. Months without a comparable saved forecast show no forecast bar. Exact values are in the table below.`}
    >
      <GroupedColumnChart
        label={`Won revenue and saved forecast by month, ${accuracyLeadLabel(lead).toLowerCase()}, ${accuracyBasisLabel(basis).toLowerCase()}`}
        series={SERIES}
        emptyMessage="No won revenue or saved forecasts in this range."
        data={accuracy.months.map((month) => {
          const selected = leadOf(month, lead);
          const comparison = comparisonOf(selected, basis);
          const actual = formatMoneyCompact(month.actual.total_amount, currency);
          return {
            key: month.period_start,
            label: formatForecastPeriodShort(month, "month"),
            fullLabel: monthName(month),
            values: [
              {
                value: month.status === "IN_PROGRESS" ? `${actual} so far` : actual,
                magnitude: magnitudeOf(month.actual.total_amount),
              },
              comparison
                ? {
                    value: formatMoneyCompact(comparison.forecast_amount, currency),
                    magnitude: magnitudeOf(comparison.forecast_amount),
                  }
                : {
                    // Never drawn as 0: the reason replaces the amount.
                    value: snapshotStatusShortText(selected?.snapshot_status ?? "MISSING"),
                    magnitude: 0,
                  },
            ],
          };
        })}
      />
    </ChartCard>
  );
}

function Muted({ children }: { children: ReactNode }) {
  return <span className="text-muted-foreground text-xs leading-5">{children}</span>;
}

/** "—" for a figure the API did not report; the reason is beside it or in the snapshot column. */
function NotReported({ reason }: { reason?: string }) {
  return (
    <span className="text-muted-foreground grid">
      <span aria-hidden="true">—</span>
      {reason ? <span className="text-xs leading-5">{reason}</span> : <span className="sr-only">Not available</span>}
    </span>
  );
}

const NOT_SCORED = "Not scored until month end";

export function ForecastAccuracyTable({ accuracy, lead, basis }: MonthsProps) {
  const { currency } = accuracy;
  const pick = (month: ForecastAccuracyMonth) => {
    const selected = leadOf(month, lead);
    return { selected, comparison: comparisonOf(selected, basis) };
  };
  const columns: DataTableColumn<ForecastAccuracyMonth>[] = [
    {
      key: "month",
      header: "Month",
      cell: (month) => (
        <span className="grid justify-items-start gap-1">
          <span className="font-medium">{formatMonth(month.period_start)}</span>
          {month.status === "IN_PROGRESS" ? <StatusBadge status="pending" label="In progress" /> : null}
        </span>
      ),
    },
    {
      key: "snapshot",
      header: "Saved forecast used",
      mobileLabel: "Snapshot",
      cell: (month) => {
        const { selected } = pick(month);
        if (!selected) return <NotReported />;
        const reason = snapshotStatusText(selected.snapshot_status, accuracy.snapshot_tolerance_days);
        const rule = selected.cutoff_rule === "BEFORE" ? "before" : "on or before";
        return (
          <span className="grid">
            {selected.captured_at ? (
              <span className="tabular-nums">{formatAbsoluteTimestamp(selected.captured_at)}</span>
            ) : null}
            {reason ? <span className="text-muted-foreground text-sm">{reason}</span> : null}
            <Muted>
              Cutoff: {rule} {formatAbsoluteTimestamp(selected.cutoff_at)}
            </Muted>
          </span>
        );
      },
    },
    {
      key: "forecast",
      header: "Forecast (est.)",
      className: "text-right",
      cell: (month) => {
        const { comparison } = pick(month);
        if (!comparison) return <NotReported />;
        return <span className="tabular-nums">{formatMoney(comparison.forecast_amount, currency)}</span>;
      },
    },
    {
      key: "actual",
      header: "Won (actual)",
      className: "text-right",
      cell: (month) => (
        <span className="grid tabular-nums">
          <span>{formatMoney(month.actual.total_amount, currency)}</span>
          <Muted>
            {dealCount(month.actual.count)}
            {month.status === "IN_PROGRESS" ? " so far" : ""}
          </Muted>
        </span>
      ),
    },
    {
      key: "variance",
      header: "Variance (actual − forecast)",
      mobileLabel: "Variance",
      className: "text-right",
      cell: (month) => {
        const { comparison } = pick(month);
        if (!comparison) return <NotReported />;
        if (comparison.accuracy_status === "MONTH_IN_PROGRESS" || comparison.variance_amount === null) {
          return <NotReported reason={NOT_SCORED} />;
        }
        return (
          <span className="grid tabular-nums">
            <span>{formatSignedMoney(comparison.variance_amount, currency)}</span>
            <Muted>{formatSignedPercent(comparison.variance_percent) ?? "No %: forecast was 0"}</Muted>
          </span>
        );
      },
    },
    {
      key: "accuracy",
      header: "Accuracy",
      className: "text-right",
      cell: (month) => {
        const { comparison } = pick(month);
        if (!comparison) return <NotReported />;
        if (comparison.accuracy_status === "MONTH_IN_PROGRESS") return <NotReported reason={NOT_SCORED} />;
        const value = formatAccuracyPercent(comparison.accuracy_percent);
        if (comparison.accuracy_status === "NO_ACTUAL_REVENUE" || value === null) {
          return <NotReported reason="No revenue won" />;
        }
        return <span className="font-medium tabular-nums">{value}</span>;
      },
    },
  ];
  return (
    <section className="grid gap-3" aria-labelledby="forecast-accuracy-months-heading">
      <SectionHeader
        id="forecast-accuracy-months-heading"
        title="Month by month"
        description={`${accuracyBasisLabel(basis)} forecast saved at ${accuracyLeadLabel(lead).toLowerCase()}, against revenue won in each UTC calendar month. Positive variance means more was won than forecast.`}
      />
      <DataTable
        columns={columns}
        rows={accuracy.months}
        getRowKey={(month) => month.period_start}
        headingLevel={3}
        tableClassName="min-w-[52rem]"
        emptyTitle="No months"
        emptyDescription="The server returned no months for this range."
      />
    </section>
  );
}
