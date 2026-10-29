"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/hooks/use-auth";
import { getPipelineForecast } from "@/lib/api/pipeline";
import { FORECAST_STALE_TIME_MS, forecastQueryKey, type ForecastUrlState } from "@/lib/forecast";

/**
 * The forecast for one horizon. Each granularity/periods pair is its own cache
 * entry, so switching never shows another horizon's figures; superseded requests
 * are aborted through the query signal.
 */
export function usePipelineForecast(state: ForecastUrlState) {
  const { session } = useAuth();
  const organizationId = session?.organization.id ?? null;
  return useQuery({
    queryKey: forecastQueryKey(organizationId, state),
    queryFn: ({ signal }) =>
      getPipelineForecast({ granularity: state.granularity, periods: state.periods }, { signal }),
    enabled: organizationId !== null,
    staleTime: FORECAST_STALE_TIME_MS,
  });
}
