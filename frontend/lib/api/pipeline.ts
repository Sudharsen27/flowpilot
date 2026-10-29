import { apiGet } from "@/lib/api/client";
import type { PipelineSummary } from "@/types/api";

/** Deterministic totals computed by the API from stored deals; never a forecast. */
export function getPipelineSummary(months = 6) {
  const clamped = Math.min(24, Math.max(1, Math.trunc(months)));
  return apiGet<PipelineSummary>(`/api/v1/pipeline/summary?months=${clamped}`);
}
