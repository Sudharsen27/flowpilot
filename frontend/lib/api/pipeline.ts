import { apiGet } from "@/lib/api/client";
import type {
  ForecastCategory,
  ForecastCategoryDeals,
  ForecastGranularity,
  PipelineForecast,
  PipelineSummary,
} from "@/types/api";

/** Deterministic totals computed by the API from stored deals; never a forecast. */
export function getPipelineSummary(months = 6) {
  const clamped = Math.min(24, Math.max(1, Math.trunc(months)));
  return apiGet<PipelineSummary>(`/api/v1/pipeline/summary?months=${clamped}`);
}

/** Stage-probability-weighted forecast. Every figure is calculated by the API. */
export function getPipelineForecast(
  params: { granularity: ForecastGranularity; periods: number },
  options: { signal?: AbortSignal } = {},
) {
  const query = new URLSearchParams({
    granularity: params.granularity,
    periods: String(params.periods),
  });
  return apiGet<PipelineForecast>(`/api/v1/pipeline/forecast?${query.toString()}`, options);
}

/**
 * The open deals behind one forecast category, for the period starting at periodStart
 * or, when it is null, the whole horizon. Totals are the API's, across every page.
 */
export function getForecastCategoryDeals(
  params: {
    category: ForecastCategory;
    granularity: ForecastGranularity;
    periods: number;
    periodStart: string | null;
    limit: number;
    offset: number;
  },
  options: { signal?: AbortSignal } = {},
) {
  const query = new URLSearchParams({
    category: params.category,
    granularity: params.granularity,
    periods: String(params.periods),
    limit: String(Math.min(100, Math.max(1, Math.trunc(params.limit)))),
    offset: String(Math.max(0, Math.trunc(params.offset))),
  });
  if (params.periodStart) query.set("period_start", params.periodStart);
  return apiGet<ForecastCategoryDeals>(`/api/v1/pipeline/forecast/deals?${query.toString()}`, options);
}
