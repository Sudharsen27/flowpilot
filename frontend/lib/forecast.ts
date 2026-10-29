import { formatMonth } from "@/lib/money";
import type { ForecastGranularity, PipelineForecast } from "@/types/api";

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

/** Forecast figures change only when deals change; a minute avoids refetch churn. */
export const FORECAST_STALE_TIME_MS = 60_000;

/** Cache key: scoped to the organization, then the exact horizon requested. */
export function forecastQueryKey(organizationId: string | null, state: ForecastUrlState) {
  return [
    "pipeline-forecast",
    organizationId,
    { granularity: state.granularity, periods: state.periods },
  ] as const;
}

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
