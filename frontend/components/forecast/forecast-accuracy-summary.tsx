import { Gauge, Scale, Target, Trophy } from "lucide-react";

import { MoneyValue } from "@/components/dashboard/dashboard-kpis";
import { MetricCard } from "@/components/data-display/metric-card";
import { MetricStrip } from "@/components/data-display/metric-strip";
import {
  closedMonthCount,
  formatAccuracyPercent,
  formatSignedMoney,
  formatSignedPercent,
  summaryOf,
} from "@/lib/forecast-accuracy";
import { formatMoneyCompact } from "@/lib/money";
import type { ForecastAccuracy, ForecastAccuracyBasis } from "@/types/api";

/** Compact on the tile, with an explicit sign; the exact amount is the accessible name. */
function SignedMoneyValue({ amount, currency }: { amount: string; currency: string }) {
  const exact = formatSignedMoney(amount, currency) ?? "";
  const negative = amount.startsWith("-");
  const compact = formatMoneyCompact(negative ? amount.slice(1) : amount, currency);
  const sign = negative ? "\u2212" : exact.startsWith("+") ? "+" : "";
  return (
    <span title={exact} aria-label={exact}>
      {sign}
      {compact}
    </span>
  );
}

function monthCount(count: number): string {
  return `${count} ${count === 1 ? "month" : "months"}`;
}

/**
 * Weighted accuracy and totals for the selected lead and basis, exactly as returned:
 * closed months with a comparable snapshot, combined by sums. Nothing is shown as 0
 * when the API has no figure.
 */
export function ForecastAccuracySummary({
  accuracy,
  lead,
  basis,
}: {
  accuracy: ForecastAccuracy;
  lead: number;
  basis: ForecastAccuracyBasis;
}) {
  const summary = summaryOf(accuracy, lead, basis);
  const { currency } = accuracy;
  const closed = closedMonthCount(accuracy);
  const shown = summary && summary.status !== "NO_COMPARABLE_MONTHS" ? summary : null;
  const noComparable =
    closed === 0
      ? "No closed month in this range yet; the month in progress is not scored."
      : "No closed month in this range has a saved forecast at this lead time.";
  const compared = summary
    ? `${summary.months_compared} of ${monthCount(closed)} compared${
        summary.months_missing > 0 ? `; ${summary.months_missing} without a saved forecast` : ""
      }.`
    : undefined;
  const accuracyValue = shown ? formatAccuracyPercent(shown.weighted_accuracy_percent) : null;
  return (
    <MetricStrip className="sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        headingLevel={3}
        label="Weighted accuracy"
        icon={<Gauge />}
        value={accuracyValue ?? undefined}
        description={compared}
        unavailableLabel={
          shown?.status === "NO_ACTUAL_REVENUE"
            ? "No revenue was won in the compared months, so accuracy is undefined."
            : noComparable
        }
      />
      <MetricCard
        headingLevel={3}
        label="Variance (actual − forecast)"
        icon={<Scale />}
        value={
          shown && shown.variance_amount !== null ? (
            <SignedMoneyValue amount={shown.variance_amount} currency={currency} />
          ) : undefined
        }
        description={
          shown
            ? shown.variance_percent === null
              ? "No percentage: the forecast total is 0."
              : `${formatSignedPercent(shown.variance_percent)} of forecast. Positive means more was won than forecast.`
            : undefined
        }
        unavailableLabel={noComparable}
      />
      <MetricCard
        headingLevel={3}
        label="Forecast total (estimate)"
        icon={<Target />}
        value={
          shown && shown.forecast_total !== null ? (
            <MoneyValue amount={shown.forecast_total} currency={currency} />
          ) : undefined
        }
        description={shown ? "Saved forecasts for the compared months." : undefined}
        unavailableLabel={noComparable}
      />
      <MetricCard
        headingLevel={3}
        label="Actual won (compared months)"
        icon={<Trophy />}
        value={
          shown && shown.actual_total !== null ? (
            <MoneyValue amount={shown.actual_total} currency={currency} />
          ) : undefined
        }
        description={shown ? "Closed won revenue in the same months, at current amounts." : undefined}
        unavailableLabel={noComparable}
      />
    </MetricStrip>
  );
}
