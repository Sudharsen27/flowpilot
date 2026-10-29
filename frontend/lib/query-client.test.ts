import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/client";
import { createQueryClient, shouldRetryQuery } from "@/lib/query-client";

describe("query retry policy", () => {
  it("never retries auth, permission, not-found or validation errors", () => {
    for (const status of [400, 401, 403, 404, 409, 422]) {
      expect(shouldRetryQuery(0, new ApiError("failed", status))).toBe(false);
    }
  });

  it("retries transient failures at most twice", () => {
    for (const error of [new ApiError("failed", 500), new ApiError("failed", 503), new ApiError("failed", 408), new ApiError("failed", 429), new TypeError("Failed to fetch")]) {
      expect(shouldRetryQuery(0, error)).toBe(true);
      expect(shouldRetryQuery(1, error)).toBe(true);
      expect(shouldRetryQuery(2, error)).toBe(false);
    }
  });

  it("applies the policy by default and accepts test overrides", () => {
    const client = createQueryClient({ retryDelay: 0 });
    const defaults = client.getDefaultOptions().queries;
    expect(defaults?.retry).toBe(shouldRetryQuery);
    expect(defaults?.retryDelay).toBe(0);
  });
});
