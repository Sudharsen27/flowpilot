"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/hooks/use-auth";
import { getForecastAccuracy } from "@/lib/api/pipeline";
import { FORECAST_STALE_TIME_MS } from "@/lib/forecast";
import { ACCURACY_LEADS, forecastAccuracyQueryKey, type AccuracyMonthRange } from "@/lib/forecast-accuracy";

/**
 * Forecast accuracy for one range of months, with every lead time. Lead and basis are
 * chosen on the page from the same response; each range is its own cache entry.
 */
export function useForecastAccuracy(range: AccuracyMonthRange) {
  const { session } = useAuth();
  const organizationId = session?.organization.id ?? null;
  return useQuery({
    queryKey: forecastAccuracyQueryKey(organizationId, range),
    queryFn: ({ signal }) =>
      getForecastAccuracy(
        { fromMonth: range.fromMonth, toMonth: range.toMonth, leadDays: ACCURACY_LEADS },
        { signal },
      ),
    enabled: organizationId !== null,
    staleTime: FORECAST_STALE_TIME_MS,
  });
}
