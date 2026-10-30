import type { ReactNode } from "react";

import { magnitudeOf, StackedBarChart, type ColumnSeries } from "@/components/charts/bar-charts";
import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { StatePanel } from "@/components/data-display/state-panel";
import { SectionHeader } from "@/components/layout/section-header";
import { Card } from "@/components/ui/card";
import { FORECAST_CATEGORY_LABELS } from "@/lib/deals";
import {
  categoryTotals,
  dealCount,
  FORECAST_CATEGORY_DISPLAY_ORDER,
  formatForecastPeriod,
  formatForecastPeriodShort,
  hasForecastCategories,
  type ForecastWithCategories,
} from "@/lib/forecast";
import { decimalEquals, formatDateOnly, formatMoney, formatMoneyCompact } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { ForecastCategory, ForecastCategoryTotals, PipelineForecast } from "@/types/api";

/** Fixed hue per category, never per rank; Pipeline stays the recessive neutral. */
const CATEGORY_MARKS: Record<ForecastCategory, string> = {
  COMMIT: "bg-chart-2",
  BEST_CASE: "bg-chart-3",
  PIPELINE: "bg-chart-4",
};

const CATEGORY_HINTS: Record<ForecastCategory, string> = {
  COMMIT: "Seller expects to close",
  BEST_CASE: "Could close with upside",
  PIPELINE: "Not yet committed",
};

const SERIES: ColumnSeries[] = FORECAST_CATEGORY_DISPLAY_ORDER.map((category) => ({
  key: category,
  label: FORECAST_CATEGORY_LABELS[category],
  markClassName: CATEGORY_MARKS[category],
}));

function Swatch({ category }: { category: ForecastCategory }) {
  return (
    <span
      className={cn("block size-2.5 shrink-0 rounded-[2px]", CATEGORY_MARKS[category])}
      aria-hidden="true"
    />
  );
}

function Amount({ amount, currency }: { amount: string; currency: string }) {
  // Exact string check: zero amounts recede so the categories with deals stand out.
  return (
    <span className={cn("tabular-nums", decimalEquals(amount, "0") && "text-muted-foreground")}>
      {formatMoney(amount, currency)}
    </span>
  );
}

function Scenario({
  term,
  amount,
  currency,
  kind,
  children,
}: {
  term: string;
  amount: string;
  currency: string;
  kind: "actual" | "scenario" | "estimate";
  children: ReactNode;
}) {
  return (
    <div className="grid content-start gap-1" data-kind={kind}>
      <dt className="text-muted-foreground text-xs font-medium">{term}</dt>
      <dd className="text-lg font-semibold tabular-nums">{formatMoney(amount, currency)}</dd>
      <dd className="text-muted-foreground text-xs leading-5">{children}</dd>
    </div>
  );
}

/**
 * Won revenue, the two category scenarios and the existing weighted forecast side by
 * side, each labelled for what it is. Every figure is the API's; nothing is added here.
 */
function ForecastScenarios({ forecast }: { forecast: ForecastWithCategories }) {
  const { currency } = forecast;
  const commit = categoryTotals(forecast.in_horizon_open, "COMMIT");
  const bestCase = categoryTotals(forecast.in_horizon_open, "BEST_CASE");
  return (
    <Card as="section" aria-labelledby="forecast-scenarios-heading" className="grid gap-4 p-4 sm:p-5">
      <div>
        <h3 id="forecast-scenarios-heading" className="text-sm font-medium">
          Scenarios for this horizon
        </h3>
        <p className="text-muted-foreground mt-0.5 text-xs leading-5">
          Commit and Best case add the full, unweighted value of open deals in those categories to
          won revenue. They are what-if totals, not guaranteed revenue. Best case already includes
          Commit; Pipeline deals are in neither.
        </p>
      </div>
      <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-4">
        <Scenario term="Won revenue (actual)" amount={forecast.won_in_horizon.total_amount} currency={currency} kind="actual">
          Already closed: {dealCount(forecast.won_in_horizon.count)} won. The base of both scenarios.
        </Scenario>
        <Scenario term="Commit scenario" amount={forecast.commit_scenario_amount} currency={currency} kind="scenario">
          Won plus the full value of {dealCount(commit.count)} in Commit.
        </Scenario>
        <Scenario
          term="Best case scenario"
          amount={forecast.best_case_scenario_amount}
          currency={currency}
          kind="scenario"
        >
          Commit scenario plus the full value of {dealCount(bestCase.count)} in Best case.
        </Scenario>
        <Scenario
          term="Projected revenue (estimate)"
          amount={forecast.projected_in_horizon_amount}
          currency={currency}
          kind="estimate"
        >
          Won plus every open deal weighted by probability, all categories included.
        </Scenario>
      </dl>
    </Card>
  );
}

function CategoryChart({ forecast }: { forecast: PipelineForecast }) {
  const { currency, granularity } = forecast;
  const unit = granularity === "quarter" ? "quarter" : "month";
  return (
    <Card as="section" aria-labelledby="forecast-category-chart-heading" className="grid content-start gap-4 p-4 sm:p-5">
      <div>
        <h3 id="forecast-category-chart-heading" className="text-sm font-medium">
          Open pipeline by category
        </h3>
        <p className="text-muted-foreground mt-0.5 text-xs leading-5">
          Full, unweighted value of open deals expected to close in each {unit}.
        </p>
      </div>
      <StackedBarChart
        label={`Open pipeline by forecast category and ${unit}`}
        categoryLabel={unit === "quarter" ? "Quarter" : "Month"}
        series={SERIES}
        emptyMessage="No open deals are expected to close in this horizon."
        data={forecast.periods.map((period) => ({
          key: period.period_start,
          label: formatForecastPeriodShort(period, granularity),
          fullLabel: formatForecastPeriod(period, granularity),
          total: formatMoneyCompact(period.open.total_amount, currency),
          values: FORECAST_CATEGORY_DISPLAY_ORDER.map((category) => {
            const row = categoryTotals(period.open, category);
            return {
              value: formatMoneyCompact(row.total_amount, currency),
              magnitude: magnitudeOf(row.total_amount),
            };
          }),
        }))}
      />
    </Card>
  );
}

type BreakdownRow = {
  key: string;
  label: string;
  hint: string;
  /** null for the total row. */
  category: ForecastCategory | null;
  totals: Pick<ForecastCategoryTotals, "count" | "total_amount" | "weighted_amount">;
};

function CategoryTable({ forecast }: { forecast: ForecastWithCategories }) {
  const { currency, in_horizon_open: inHorizon } = forecast;
  const rows: BreakdownRow[] = [
    ...FORECAST_CATEGORY_DISPLAY_ORDER.map((category) => ({
      key: category,
      label: FORECAST_CATEGORY_LABELS[category],
      hint: CATEGORY_HINTS[category],
      category,
      totals: categoryTotals(inHorizon, category),
    })),
    { key: "total", label: "All open in horizon", hint: "Every category", category: null, totals: inHorizon },
  ];
  const columns: DataTableColumn<BreakdownRow>[] = [
    {
      key: "category",
      header: "Category",
      cell: (row) => (
        <span className="flex items-start gap-2">
          {row.category ? <span className="mt-1"><Swatch category={row.category} /></span> : null}
          <span className="grid">
            <span className="font-medium">{row.label}</span>
            <span className="text-muted-foreground text-xs">{row.hint}</span>
          </span>
        </span>
      ),
    },
    {
      key: "count",
      header: "Deals",
      className: "text-right",
      cell: (row) => (
        <span className={cn("tabular-nums", row.totals.count === 0 && "text-muted-foreground")}>
          {row.totals.count}
        </span>
      ),
    },
    {
      key: "full",
      header: "Full amount",
      className: "text-right",
      cell: (row) => <Amount amount={row.totals.total_amount} currency={currency} />,
    },
    {
      key: "weighted",
      header: "Weighted (est.)",
      className: "text-right",
      cell: (row) => <Amount amount={row.totals.weighted_amount} currency={currency} />,
    },
  ];
  return (
    <DataTable
      columns={columns}
      rows={rows}
      getRowKey={(row) => row.key}
      headingLevel={3}
      // Four short columns: fits beside the chart without a horizontal scroll.
      tableClassName="min-w-0"
    />
  );
}

/** Open pipeline in the horizon by forecast category, and the scenarios built from it. */
export function ForecastCategories({ forecast }: { forecast: PipelineForecast }) {
  return (
    <section className="grid gap-3" aria-labelledby="forecast-categories-heading">
      <SectionHeader
        id="forecast-categories-heading"
        title="Forecast categories"
        description={`Open deals expected to close ${formatDateOnly(forecast.horizon_start)} – ${formatDateOnly(forecast.horizon_end)}, grouped by the seller's forecast category. Past-due and beyond-horizon deals are not included.`}
      />
      {hasForecastCategories(forecast) ? (
        <>
          <ForecastScenarios forecast={forecast} />
          <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <CategoryChart forecast={forecast} />
            <CategoryTable forecast={forecast} />
          </div>
        </>
      ) : (
        <StatePanel
          kind="unavailable"
          className="max-w-none"
          title="Category totals unavailable"
          description="The server did not return forecast category totals, so scenarios cannot be shown. The rest of the forecast is unaffected. Try again once the server has been updated."
        />
      )}
    </section>
  );
}
