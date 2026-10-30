"use client";

import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { AUTH_SESSION_INVALIDATED_EVENT } from "@/lib/auth/storage";
import { DEALS_CHANGED_EVENT } from "@/lib/deal-events";
import { FORECAST_QUERY_ROOTS } from "@/lib/forecast";
import { createQueryClient } from "@/lib/query-client";

/**
 * Query cache for the signed-in workspace. Cached data never outlives the session:
 * the cache is cleared whenever the token is cleared (sign-out or a 401). Figures
 * derived from deals are invalidated after every deal write: on-screen queries refetch
 * at once, and cached ones refetch the next time they are shown.
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
    window.addEventListener(AUTH_SESSION_INVALIDATED_EVENT, clear);
    window.addEventListener(DEALS_CHANGED_EVENT, refreshDealFigures);
    return () => {
      window.removeEventListener(AUTH_SESSION_INVALIDATED_EVENT, clear);
      window.removeEventListener(DEALS_CHANGED_EVENT, refreshDealFigures);
    };
  }, [queryClient]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
