import { Target } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { StatePanel } from "@/components/data-display/state-panel";
import { SectionHeader } from "@/components/layout/section-header";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  FORECAST_TARGET_BASIS_ORDER,
  formatForecastPeriod,
  hasForecastTargets,
  type ForecastPeriodWithTargets,
  type ForecastWithTargets,
} from "@/lib/forecast";
import { decimalEquals, formatDateOnly, formatMoney, formatMonth } from "@/lib/money";
import { salesTargetsHref } from "@/lib/sales-targets";
import { cn } from "@/lib/utils";
import type {
  ForecastTarget,
  ForecastTargetBasis,
  ForecastTargetComparison,
  PipelineForecast,
} from "@/types/api";

export const TARGET_BASIS_LABELS: Record<ForecastTargetBasis, string> = {
  WON: "Won to date (actual)",
  COMMIT_SCENARIO: "Commit scenario",
  BEST_CASE_SCENARIO: "Best case scenario",
  PROJECTED: "Projected (estimate)",
};

const TARGET_BASIS_HINTS: Record<ForecastTargetBasis, string> = {
  WON: "Revenue already closed",
  COMMIT_SCENARIO: "Won plus full Commit amounts",
  BEST_CASE_SCENARIO: "Commit scenario plus full Best case amounts",
  PROJECTED: "Won plus probability-weighted open deals",
};

/** Same marks as elsewhere on the page: solid for actual, dashed for the estimate. */
const TARGET_BASIS_MARKS: Record<ForecastTargetBasis, string> = {
  WON: "bg-chart-1",
  COMMIT_SCENARIO: "bg-chart-2",
  BEST_CASE_SCENARIO: "bg-chart-3",
  PROJECTED: "bg-chart-2/40 border border-dashed border-chart-2",
};

/** Missing months listed in full up to this many; the rest are counted. */
const MISSING_MONTHS_SHOWN = 6;

function percentText(comparison: ForecastTargetComparison): string {
  return comparison.attainment_percent === null
    ? "Target is 0"
    : `${comparison.attainment_percent}% of target`;
}

/** Remaining or above, whichever the API reports as non-zero; both zero is on target. */
function gapText(comparison: ForecastTargetComparison, currency: string): string {
  if (!decimalEquals(comparison.above_target_amount, "0")) {
    return `Above target by ${formatMoney(comparison.above_target_amount, currency)}`;
  }
  if (!decimalEquals(comparison.remaining_amount, "0")) {
    return `${formatMoney(comparison.remaining_amount, currency)} to go`;
  }
  return "On target";
}

/**
 * Decorative progress bar sized from the API's percentage; the same facts are in the
 * text beside it. The bar's end is the target, so anything at or above 100% fills it.
 */
function ProgressBar({ comparison }: { comparison: ForecastTargetComparison }) {
  // A zero target has no percentage: any amount above it fills the bar.
  const zeroTargetFill = decimalEquals(comparison.amount, "0") ? 0 : 100;
  const percent =
    comparison.attainment_percent === null ? zeroTargetFill : Number(comparison.attainment_percent);
  const width = Number.isFinite(percent) ? Math.min(100, Math.max(0, percent)) : 0;
  return (
    <span className="bg-muted relative block h-2 overflow-hidden rounded-full" aria-hidden="true">
      <span
        data-testid="target-progress"
        className={cn("absolute inset-y-0 left-0 rounded-full", TARGET_BASIS_MARKS[comparison.basis])}
        style={{ width: `${width}%` }}
      />
    </span>
  );
}

function missingMonthsText(months: string[]): string {
  const shown = months.slice(0, MISSING_MONTHS_SHOWN).map(formatMonth).join(", ");
  const rest = months.length - MISSING_MONTHS_SHOWN;
  return rest > 0 ? `${shown} and ${rest} more` : shown;
}

/** "Set targets" for owners and admins, opening the year of the first missing month. */
function SetTargetsLink({ target, canManage }: { target: ForecastTarget; canManage: boolean }) {
  const first = target.missing_months[0];
  if (!canManage || !first) return null;
  return (
    <Link href={salesTargetsHref(first)} className={buttonVariants({ variant: "outline", size: "sm" })}>
      <Target aria-hidden="true" />
      Set targets
    </Link>
  );
}

function OwnerTargetsHint({ target, scope }: { target: ForecastTarget; scope: string }) {
  if (!target.has_owner_targets) return null;
  return (
    <p className="text-muted-foreground text-xs leading-5" role="note">
      Owner targets exist for {scope}, but they are set per person and are not added together into
      an organization target.
    </p>
  );
}

/** Status text for a target that is not FULL; null when it is. */
function incompleteSummary(target: ForecastTarget): { title: string; detail: string } | null {
  if (target.status === "NONE") {
    return {
      title: "No organization target set",
      detail: `None of the ${target.months_in_range} ${target.months_in_range === 1 ? "month" : "months"} has an organization target.`,
    };
  }
  if (target.status === "PARTIAL") {
    return {
      title: `Target incomplete: ${target.months_with_target} of ${target.months_in_range} months set`,
      detail: `Missing: ${missingMonthsText(target.missing_months)}. Attainment is shown once every month has a target.`,
    };
  }
  return null;
}

function HorizonTarget({
  forecast,
  canManage,
}: {
  forecast: ForecastWithTargets;
  canManage: boolean;
}) {
  const { currency, target_in_horizon: target } = forecast;
  const incomplete = incompleteSummary(target);
  return (
    <Card
      as="section"
      aria-labelledby="forecast-target-horizon-heading"
      className="grid gap-4 p-4 sm:p-5"
      data-status={target.status}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 id="forecast-target-horizon-heading" className="text-sm font-medium">
            Target for this horizon
          </h3>
          <p className="text-muted-foreground mt-0.5 text-xs leading-5">
            {formatDateOnly(forecast.horizon_start)} – {formatDateOnly(forecast.horizon_end)}
          </p>
        </div>
        {target.amount !== null ? (
          <div className="sm:text-right">
            <p className="text-lg font-semibold tabular-nums">{formatMoney(target.amount, currency)}</p>
            <p className="text-muted-foreground text-xs">
              {target.status === "FULL" ? "Organization target" : "Partial target (months set so far)"}
            </p>
          </div>
        ) : null}
      </div>

      {incomplete ? (
        <div className="grid gap-3">
          <div className="grid gap-1">
            <p className="text-sm font-medium">{incomplete.title}</p>
            <p className="text-muted-foreground text-sm leading-6">{incomplete.detail}</p>
          </div>
          <OwnerTargetsHint target={target} scope="this horizon" />
          {canManage ? (
            <div>
              <SetTargetsLink target={target} canManage={canManage} />
            </div>
          ) : (
            <p className="text-muted-foreground text-xs leading-5">
              Owners and admins can set organization targets.
            </p>
          )}
        </div>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2" aria-label="Progress to target">
          {target.comparisons.map((comparison) => (
            <li key={comparison.basis} className="grid gap-1.5" data-basis={comparison.basis}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="grid min-w-0">
                  <span className="text-sm font-medium">{TARGET_BASIS_LABELS[comparison.basis]}</span>
                  <span className="text-muted-foreground text-xs">{TARGET_BASIS_HINTS[comparison.basis]}</span>
                </span>
                <span className="shrink-0 text-right text-sm font-semibold tabular-nums">
                  {formatMoney(comparison.amount, currency)}
                </span>
              </div>
              <ProgressBar comparison={comparison} />
              <div className="text-muted-foreground flex flex-wrap justify-between gap-x-3 text-xs tabular-nums">
                <span>{percentText(comparison)}</span>
                <span>{gapText(comparison, currency)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function FigureCell({
  amount,
  comparison,
  currency,
}: {
  amount: string;
  comparison: ForecastTargetComparison | undefined;
  currency: string;
}) {
  return (
    <span className="grid tabular-nums">
      <span className={cn(decimalEquals(amount, "0") && "text-muted-foreground")}>
        {formatMoney(amount, currency)}
      </span>
      {comparison ? <span className="text-muted-foreground text-xs">{percentText(comparison)}</span> : null}
    </span>
  );
}

function TargetCell({ target, currency }: { target: ForecastTarget; currency: string }): ReactNode {
  if (target.status === "NONE") {
    return (
      <span className="text-muted-foreground grid">
        <span>Not set</span>
        {target.has_owner_targets ? <span className="text-xs">Owner targets only</span> : null}
      </span>
    );
  }
  return (
    <span className="grid tabular-nums">
      <span>{formatMoney(target.amount, currency)}</span>
      {target.status === "PARTIAL" ? (
        <span className="text-warning-text text-xs">
          Partial: {target.months_with_target} of {target.months_in_range} months
        </span>
      ) : null}
    </span>
  );
}

type TargetPeriod = ForecastPeriodWithTargets;

/** The period's own figure for a basis; with a FULL target it equals the comparison amount. */
function periodFigure(period: TargetPeriod, basis: ForecastTargetBasis): string {
  switch (basis) {
    case "WON":
      return period.won.total_amount;
    case "COMMIT_SCENARIO":
      return period.commit_scenario_amount;
    case "BEST_CASE_SCENARIO":
      return period.best_case_scenario_amount;
    case "PROJECTED":
      return period.projected_amount;
  }
}

function PeriodTargetTable({ forecast }: { forecast: ForecastWithTargets }) {
  const { currency, granularity } = forecast;
  const comparison = (period: TargetPeriod, basis: ForecastTargetBasis) =>
    period.target.comparisons.find((row) => row.basis === basis);
  const columns: DataTableColumn<TargetPeriod>[] = [
    {
      key: "period",
      header: "Period",
      cell: (period) => <span className="font-medium">{formatForecastPeriod(period, granularity)}</span>,
    },
    {
      key: "target",
      header: "Target",
      className: "text-right",
      cell: (period) => <TargetCell target={period.target} currency={currency} />,
    },
    ...FORECAST_TARGET_BASIS_ORDER.map(
      (basis): DataTableColumn<TargetPeriod> => ({
        key: basis,
        header: TARGET_BASIS_LABELS[basis],
        className: "text-right",
        cell: (period) => (
          <FigureCell amount={periodFigure(period, basis)} comparison={comparison(period, basis)} currency={currency} />
        ),
      }),
    ),
  ];
  return (
    <DataTable
      columns={columns}
      rows={forecast.periods}
      getRowKey={(period) => period.period_start}
      headingLevel={3}
      tableClassName="min-w-[48rem]"
      emptyTitle="No forecast periods"
      emptyDescription="The forecast returned no periods for this horizon."
    />
  );
}

/**
 * Organization-wide sales targets against won revenue, the two scenarios and the
 * weighted projection. Every amount and percentage is the API's; attainment appears
 * only for FULL targets, never against a partial or missing one.
 */
export function ForecastTargets({
  forecast,
  canManageTargets,
}: {
  forecast: PipelineForecast;
  canManageTargets: boolean;
}) {
  const unit = forecast.granularity === "quarter" ? "quarter" : "month";
  return (
    <section className="grid gap-3" aria-labelledby="forecast-targets-heading">
      <SectionHeader
        id="forecast-targets-heading"
        title="Progress to target"
        description={`Organization-wide monthly sales targets; a ${unit === "quarter" ? "quarter's target is the sum of its three months" : "month's target is compared with that month"}. Won is revenue to date; scenarios and the projection are estimates, not committed revenue.`}
      />
      {hasForecastTargets(forecast) ? (
        <>
          <HorizonTarget forecast={forecast} canManage={canManageTargets} />
          <PeriodTargetTable forecast={forecast} />
          {forecast.target_in_horizon.status === "FULL" ? null : (
            <p className="text-muted-foreground text-xs leading-5">
              Percentages appear only for periods where every month has an organization target.
            </p>
          )}
        </>
      ) : (
        <StatePanel
          kind="unavailable"
          className="max-w-none"
          title="Target comparison unavailable"
          description="The server did not return sales target figures, so progress to target cannot be shown. The rest of the forecast is unaffected. Try again once the server has been updated."
        />
      )}
    </section>
  );
}
