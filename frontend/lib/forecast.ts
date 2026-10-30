import { formatMonth } from "@/lib/money";
import type {
  ForecastCategory,
  ForecastCategoryTotals,
  ForecastGranularity,
  ForecastOpenTotals,
  ForecastPeriod,
  ForecastTarget,
  ForecastTargetBasis,
  PipelineForecast,
} from "@/types/api";

/**
 * URL state and labels for the forecast page. Nothing here touches amounts: every
 * figure on the page is a string returned by the API.
 */

export const FORECAST_PATH = "/forecast";

/** Defaults and backend limits (`periods` is 1..24 months or 1..8 quarters). */
export const FORECAST_PERIOD_RULES: Record<
  ForecastGranularity,
  { defaultPeriods: number; max: number; options: readonly number[] }
> = {
  quarter: { defaultPeriods: 4, max: 8, options: [2, 4, 6, 8] },
  month: { defaultPeriods: 12, max: 24, options: [3, 6, 12, 18, 24] },
};

export type ForecastUrlState = {
  granularity: ForecastGranularity;
  periods: number;
};

/** Root of the forecast query key; refreshed after deal writes and target saves. */
export const FORECAST_QUERY_ROOT = "pipeline-forecast";

/** Forecast figures change only when deals change; a minute avoids refetch churn. */
export const FORECAST_STALE_TIME_MS = 60_000;

/** Cache key: scoped to the organization, then the exact horizon requested. */
export function forecastQueryKey(organizationId: string | null, state: ForecastUrlState) {
  return [
    FORECAST_QUERY_ROOT,
    organizationId,
    { granularity: state.granularity, periods: state.periods },
  ] as const;
}

/** One page of a category drill-down. */
export const FORECAST_DEALS_PAGE_SIZE = 20;

export type ForecastDealsSelection = {
  category: ForecastCategory;
  /** A period's start, or null for the whole horizon. */
  periodStart: string | null;
};

/** Cache key: the organization, then the horizon, category, period and page. */
export function forecastDealsQueryKey(
  organizationId: string | null,
  state: ForecastUrlState,
  selection: ForecastDealsSelection,
  offset: number,
) {
  return [
    "pipeline-forecast-deals",
    organizationId,
    {
      granularity: state.granularity,
      periods: state.periods,
      category: selection.category,
      periodStart: selection.periodStart,
      limit: FORECAST_DEALS_PAGE_SIZE,
      offset,
    },
  ] as const;
}

/** Every cached query derived from deals on this page; refreshed after any deal write. */
export const FORECAST_QUERY_ROOTS = [FORECAST_QUERY_ROOT, "pipeline-forecast-deals"] as const;

export function parseForecastSearchParams(searchParams: URLSearchParams): ForecastUrlState {
  const granularity: ForecastGranularity =
    searchParams.get("granularity")?.trim().toLowerCase() === "month" ? "month" : "quarter";
  const rules = FORECAST_PERIOD_RULES[granularity];
  const raw = searchParams.get("periods")?.trim() ?? "";
  const periods = /^\d{1,2}$/.test(raw) ? Number.parseInt(raw, 10) : rules.defaultPeriods;
  return {
    granularity,
    periods: periods >= 1 && periods <= rules.max ? periods : rules.defaultPeriods,
  };
}

/** Defaults are omitted so the plain /forecast URL stays canonical. */
export function serializeForecastSearchParams(state: ForecastUrlState): string {
  const query = new URLSearchParams();
  if (state.granularity !== "quarter") query.set("granularity", state.granularity);
  if (state.periods !== FORECAST_PERIOD_RULES[state.granularity].defaultPeriods) {
    query.set("periods", String(state.periods));
  }
  return query.toString();
}

/** Horizon choices, including a valid value that arrived through the URL. */
export function forecastPeriodOptions(granularity: ForecastGranularity, current: number): number[] {
  return [...new Set([...FORECAST_PERIOD_RULES[granularity].options, current])].sort((a, b) => a - b);
}

export function forecastHorizonLabel(granularity: ForecastGranularity, periods: number): string {
  const unit = granularity === "quarter" ? "quarter" : "month";
  return `${periods} ${unit}${periods === 1 ? "" : "s"}`;
}

const QUARTER_LABEL = /^(\d{4})-Q([1-4])$/;

/** "2026-Q4" → "Q4 2026"; months use the period start, e.g. "November 2026". */
export function formatForecastPeriod(
  period: { label: string; period_start: string },
  granularity: ForecastGranularity,
): string {
  if (granularity === "quarter") {
    const match = QUARTER_LABEL.exec(period.label);
    return match ? `Q${match[2]} ${match[1]}` : period.label;
  }
  return formatMonth(period.period_start);
}

/** Axis label: "Q4 2026" or "Nov 26". */
export function formatForecastPeriodShort(
  period: { label: string; period_start: string },
  granularity: ForecastGranularity,
): string {
  if (granularity === "quarter") return formatForecastPeriod(period, granularity);
  const date = new Date(`${period.period_start}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return period.label;
  return new Intl.DateTimeFormat("en", {
    month: "short",
    year: "2-digit",
    timeZone: "UTC",
  }).format(date);
}

export const FORECAST_METHOD_LABELS: Record<PipelineForecast["method"], string> = {
  STAGE_PROBABILITY_WEIGHTED: "Stage-probability weighted",
};

export const FORECAST_ROUNDING_LABELS: Record<PipelineForecast["rounding"], string> = {
  PER_DEAL_HALF_UP_CENTS:
    "Each deal's weighted value is rounded half-up to the cent once; totals are sums of those cents.",
};

/** Labels for API codes, falling back to the raw code if the API adds a new one. */
export function forecastMethodLabel(method: string): string {
  return FORECAST_METHOD_LABELS[method as PipelineForecast["method"]] ?? method;
}

export function forecastRoundingLabel(rounding: string): string {
  return FORECAST_ROUNDING_LABELS[rounding as PipelineForecast["rounding"]] ?? rounding;
}

/** True when there is nothing to forecast: no open deals and nothing won in the horizon. */
export function isForecastEmpty(forecast: PipelineForecast): boolean {
  return forecast.open_pipeline.count === 0 && forecast.won_in_horizon.count === 0;
}

export function dealCount(count: number): string {
  return `${count} ${count === 1 ? "deal" : "deals"}`;
}

/** Most to least confident, the order the cumulative scenarios build up in. */
export const FORECAST_CATEGORY_DISPLAY_ORDER: readonly ForecastCategory[] = [
  "COMMIT",
  "BEST_CASE",
  "PIPELINE",
];

/** A forecast whose API returned category totals and scenarios (Slice 4C-2 onwards). */
export type ForecastWithCategories = PipelineForecast &
  Required<
    Pick<PipelineForecast, "in_horizon_open" | "commit_scenario_amount" | "best_case_scenario_amount">
  >;

/**
 * False when an older API answered (for example a backend not yet restarted after a
 * deploy): the category figures are missing and must not be shown as zero.
 */
export function hasForecastCategories(forecast: PipelineForecast): forecast is ForecastWithCategories {
  return (
    forecast.in_horizon_open?.category_totals !== undefined &&
    forecast.commit_scenario_amount !== undefined &&
    forecast.best_case_scenario_amount !== undefined
  );
}

/** One category's totals in a bucket, exactly as returned; zeros if the API omitted it. */
export function categoryTotals(
  totals: ForecastOpenTotals | undefined,
  category: ForecastCategory,
): ForecastCategoryTotals {
  return (
    totals?.category_totals?.find((row) => row.category === category) ?? {
      category,
      count: 0,
      total_amount: "0.00",
      weighted_amount: "0.00",
    }
  );
}

/** The figures compared with a target, in the API's order. */
export const FORECAST_TARGET_BASIS_ORDER: readonly ForecastTargetBasis[] = [
  "WON",
  "COMMIT_SCENARIO",
  "BEST_CASE_SCENARIO",
  "PROJECTED",
];

export type ForecastPeriodWithTargets = ForecastPeriod &
  Required<Pick<ForecastPeriod, "commit_scenario_amount" | "best_case_scenario_amount" | "target">>;

/** A forecast whose API returned sales target comparisons (Slice 4D onwards). */
export type ForecastWithTargets = Omit<PipelineForecast, "periods"> & {
  periods: ForecastPeriodWithTargets[];
  target_in_horizon: ForecastTarget;
};

/**
 * False when an older API answered: target figures are missing and must not be shown as
 * "no target set".
 */
export function hasForecastTargets(forecast: PipelineForecast): forecast is ForecastWithTargets {
  return (
    forecast.target_in_horizon !== undefined &&
    forecast.periods.every(
      (period) =>
        period.target !== undefined &&
        period.commit_scenario_amount !== undefined &&
        period.best_case_scenario_amount !== undefined,
    )
  );
}
