"use client";

import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { AUTH_SESSION_INVALIDATED_EVENT } from "@/lib/auth/storage";
import { DEALS_CHANGED_EVENT, SALES_TARGETS_CHANGED_EVENT } from "@/lib/deal-events";
import { FORECAST_QUERY_ROOT, FORECAST_QUERY_ROOTS } from "@/lib/forecast";
import { createQueryClient } from "@/lib/query-client";

/**
 * Query cache for the signed-in workspace. Cached data never outlives the session:
 * the cache is cleared whenever the token is cleared (sign-out or a 401). Figures
 * derived from deals are invalidated after every deal write: on-screen queries refetch
 * at once, and cached ones refetch the next time they are shown. A sales target save
 * invalidates only the forecast itself; drill-down deal lists do not use targets.
 */
export function QueryProvider({ children, client }: { children: ReactNode; client?: QueryClient }) {
  const [queryClient] = useState(() => client ?? createQueryClient());

  useEffect(() => {
    const clear = () => queryClient.clear();
    const refreshDealFigures = () => {
      for (const root of FORECAST_QUERY_ROOTS) {
        void queryClient.invalidateQueries({ queryKey: [root] });
      }
    };
    const refreshTargetFigures = () => {
      void queryClient.invalidateQueries({ queryKey: [FORECAST_QUERY_ROOT] });
    };
    window.addEventListener(AUTH_SESSION_INVALIDATED_EVENT, clear);
    window.addEventListener(DEALS_CHANGED_EVENT, refreshDealFigures);
    window.addEventListener(SALES_TARGETS_CHANGED_EVENT, refreshTargetFigures);
    return () => {
      window.removeEventListener(AUTH_SESSION_INVALIDATED_EVENT, clear);
      window.removeEventListener(DEALS_CHANGED_EVENT, refreshDealFigures);
      window.removeEventListener(SALES_TARGETS_CHANGED_EVENT, refreshTargetFigures);
    };
  }, [queryClient]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
