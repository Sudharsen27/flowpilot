import { QueryClient, type QueryClientConfig } from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";

const MAX_RETRIES = 2;

/**
 * Retry only failures that can succeed on a second attempt: network errors, 5xx,
 * 408 and 429. Other 4xx responses (401/403 auth, 404, 422 validation) are final.
 */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (
    error instanceof ApiError &&
    error.status >= 400 &&
    error.status < 500 &&
    error.status !== 408 &&
    error.status !== 429
  ) {
    return false;
  }
  return failureCount < MAX_RETRIES;
}

/** One client per mounted workspace; tests pass overrides such as `retryDelay: 0`. */
export function createQueryClient(
  queryDefaults: NonNullable<QueryClientConfig["defaultOptions"]>["queries"] = {},
): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetryQuery,
        ...queryDefaults,
      },
    },
  });
}
