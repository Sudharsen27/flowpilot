import { GroupedColumnChart, magnitudeOf, type ColumnSeries } from "@/components/charts/bar-charts";
import { ChartCard } from "@/components/charts/chart-card";
import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { SectionHeader } from "@/components/layout/section-header";
import { dealCount, formatForecastPeriod, formatForecastPeriodShort } from "@/lib/forecast";
import { decimalEquals, formatDateOnly, formatMoney, formatMoneyCompact } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { ForecastPeriod, PipelineForecast } from "@/types/api";

/** Solid for what happened; outlined and tinted for the estimate. */
const SERIES: ColumnSeries[] = [
  { key: "won", label: "Won revenue (actual)", markClassName: "bg-chart-1" },
  {
    key: "weighted",
    label: "Weighted forecast (estimate)",
    markClassName: "bg-chart-2/40 border border-dashed border-chart-2",
  },
];

function Amount({ amount, currency, count }: { amount: string; currency: string; count?: number }) {
  // Exact string check: zero rows recede so the periods with activity stand out.
  const zero = decimalEquals(amount, "0");
  return (
    <span className={cn("grid tabular-nums", zero && "text-muted-foreground")}>
      <span>{formatMoney(amount, currency)}</span>
      {count === undefined ? null : (
        <span className="text-muted-foreground text-xs">{dealCount(count)}</span>
      )}
    </span>
  );
}

export function ForecastChart({ forecast }: { forecast: PipelineForecast }) {
  const unit = forecast.granularity === "quarter" ? "quarter" : "month";
  return (
    <ChartCard
      title="Won revenue and weighted forecast"
      description={`Actual won revenue and probability-weighted open pipeline, by ${unit}. Weighted forecast is an estimate, not committed revenue. Exact values are in the table below.`}
    >
      <GroupedColumnChart
        label={`Won revenue and weighted forecast by ${unit}`}
        series={SERIES}
        emptyMessage="No won revenue or open pipeline in this horizon."
        data={forecast.periods.map((period) => ({
          key: period.period_start,
          label: formatForecastPeriodShort(period, forecast.granularity),
          fullLabel: formatForecastPeriod(period, forecast.granularity),
          values: [
            {
              value: formatMoneyCompact(period.won.total_amount, forecast.currency),
              magnitude: magnitudeOf(period.won.total_amount),
            },
            {
              value: formatMoneyCompact(period.open.weighted_amount, forecast.currency),
              magnitude: magnitudeOf(period.open.weighted_amount),
            },
          ],
        }))}
      />
    </ChartCard>
  );
}

export function ForecastPeriodTable({ forecast }: { forecast: PipelineForecast }) {
  const { currency, granularity } = forecast;
  const columns: DataTableColumn<ForecastPeriod>[] = [
    {
      key: "period",
      header: "Period",
      cell: (period) => (
        <span className="grid">
          <span className="font-medium">{formatForecastPeriod(period, granularity)}</span>
          <span className="text-muted-foreground text-xs">
            {formatDateOnly(period.period_start)} – {formatDateOnly(period.period_end)}
          </span>
        </span>
      ),
    },
    {
      key: "won",
      header: "Won (actual)",
      className: "text-right",
      cell: (period) => <Amount amount={period.won.total_amount} currency={currency} count={period.won.count} />,
    },
    {
      key: "open",
      header: "Open pipeline",
      className: "text-right",
      cell: (period) => <Amount amount={period.open.total_amount} currency={currency} count={period.open.count} />,
    },
    {
      key: "weighted",
      header: "Weighted forecast (est.)",
      mobileLabel: "Weighted (est.)",
      className: "text-right",
      cell: (period) => <Amount amount={period.open.weighted_amount} currency={currency} />,
    },
    {
      key: "projected",
      header: "Projected (est.)",
      className: "text-right",
      cell: (period) => <Amount amount={period.projected_amount} currency={currency} />,
    },
  ];
  return (
    <section className="grid gap-3" aria-labelledby="forecast-periods-heading">
      <SectionHeader
        id="forecast-periods-heading"
        title={`Forecast by ${granularity}`}
        description="Won is revenue already closed in the period. Open pipeline counts deals expected to close in the period; weighted forecast and projected are estimates."
      />
      <DataTable
        columns={columns}
        rows={forecast.periods}
        getRowKey={(period) => period.period_start}
        headingLevel={3}
        // Five short columns fit tablet and sidebar-open laptop widths without scrolling.
        tableClassName="min-w-[42rem]"
        emptyTitle="No forecast periods"
        emptyDescription="The forecast returned no periods for this horizon."
      />
    </section>
  );
}
