"use client";

import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { AUTH_SESSION_INVALIDATED_EVENT } from "@/lib/auth/storage";
import { createQueryClient } from "@/lib/query-client";

/**
 * Query cache for the signed-in workspace. Cached data never outlives the session:
 * the cache is cleared whenever the token is cleared (sign-out or a 401).
 */
export function QueryProvider({ children, client }: { children: ReactNode; client?: QueryClient }) {
  const [queryClient] = useState(() => client ?? createQueryClient());

  useEffect(() => {
    const clear = () => queryClient.clear();
    window.addEventListener(AUTH_SESSION_INVALIDATED_EVENT, clear);
    return () => window.removeEventListener(AUTH_SESSION_INVALIDATED_EVENT, clear);
  }, [queryClient]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
