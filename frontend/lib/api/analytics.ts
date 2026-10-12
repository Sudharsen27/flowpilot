import { apiGet } from "@/lib/api/client";
import type {
  AnalyticsRangeDays,
  AnalyticsSummary,
  LeadSource,
} from "@/types/api";

export function getAnalyticsSummary(
  params: { rangeDays?: AnalyticsRangeDays; source?: LeadSource | null } = {},
) {
  const query = new URLSearchParams();
  query.set("range_days", String(params.rangeDays ?? 30));
  if (params.source) {
    query.set("source", params.source);
  }
  return apiGet<AnalyticsSummary>(
    `/api/v1/analytics/summary?${query.toString()}`,
  );
}
