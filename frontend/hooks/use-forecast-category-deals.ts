"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/hooks/use-auth";
import { getForecastCategoryDeals } from "@/lib/api/pipeline";
import {
  FORECAST_DEALS_PAGE_SIZE,
  FORECAST_STALE_TIME_MS,
  forecastDealsQueryKey,
  type ForecastDealsSelection,
  type ForecastUrlState,
} from "@/lib/forecast";

/**
 * One page of the deals behind a forecast category. While another page of the same
 * category and period loads, the previous page stays on screen; any other selection
 * starts empty so its figures are never mistaken for another's. Superseded requests
 * are aborted through the query signal. Pass null while nothing is selected.
 *
 * notBefore (a dataUpdatedAt timestamp) marks cached pages fetched earlier as stale, so
 * they are fetched again; used after a page correction, when older pages are outdated.
 */
export function useForecastCategoryDeals(
  state: ForecastUrlState,
  selection: ForecastDealsSelection | null,
  offset: number,
  notBefore = 0,
) {
  const { session } = useAuth();
  const organizationId = session?.organization.id ?? null;
  const fallback: ForecastDealsSelection = selection ?? { category: "COMMIT", periodStart: null };
  const queryKey = forecastDealsQueryKey(organizationId, state, fallback, offset);
  return useQuery({
    queryKey,
    queryFn: ({ signal }) =>
      getForecastCategoryDeals(
        {
          category: fallback.category,
          granularity: state.granularity,
          periods: state.periods,
          periodStart: fallback.periodStart,
          limit: FORECAST_DEALS_PAGE_SIZE,
          offset,
        },
        { signal },
      ),
    enabled: organizationId !== null && selection !== null,
    staleTime: (query) => (query.state.dataUpdatedAt < notBefore ? 0 : FORECAST_STALE_TIME_MS),
    placeholderData: (previous, previousQuery) => {
      const before = previousQuery?.queryKey[2];
      const now = queryKey[2];
      const samePages =
        previousQuery?.queryKey[1] === organizationId &&
        typeof before === "object" &&
        before.granularity === now.granularity &&
        before.periods === now.periods &&
        before.category === now.category &&
        before.periodStart === now.periodStart;
      return samePages ? previous : undefined;
    },
  });
}
