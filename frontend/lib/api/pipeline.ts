import { apiGet } from "@/lib/api/client";
import type { ForecastGranularity, PipelineForecast, PipelineSummary } from "@/types/api";

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
