import { render, screen } from "@testing-library/react";
import { useQueryClient } from "@tanstack/react-query";
import { act } from "react";
import { describe, expect, it } from "vitest";

import { QueryProvider } from "@/components/providers/query-provider";
import { clearAccessToken } from "@/lib/auth/storage";
import { notifyDealsChanged } from "@/lib/deal-events";
import { createQueryClient } from "@/lib/query-client";

function Probe() {
  const client = useQueryClient();
  return <p>{client === undefined ? "missing" : "client ready"}</p>;
}

describe("QueryProvider", () => {
  it("provides a query client to the workspace", () => {
    render(
      <QueryProvider>
        <Probe />
      </QueryProvider>,
    );
    expect(screen.getByText("client ready")).toBeInTheDocument();
  });

  it("drops cached data when the session is invalidated", () => {
    const client = createQueryClient();
    client.setQueryData(["pipeline-forecast", "org-1", { granularity: "quarter", periods: 4 }], {
      currency: "INR",
    });
    render(
      <QueryProvider client={client}>
        <Probe />
      </QueryProvider>,
    );
    expect(client.getQueryCache().getAll()).toHaveLength(1);
    act(() => clearAccessToken());
    expect(client.getQueryCache().getAll()).toHaveLength(0);
  });

  it("invalidates forecast and drill-down queries after a deal write, and nothing else", () => {
    const client = createQueryClient();
    const forecastKey = ["pipeline-forecast", "org-1", { granularity: "quarter", periods: 4 }];
    const dealsKey = ["pipeline-forecast-deals", "org-1", { category: "COMMIT", offset: 0 }];
    const otherKey = ["leads", "org-1"];
    for (const key of [forecastKey, dealsKey, otherKey]) client.setQueryData(key, { cached: true });
    render(
      <QueryProvider client={client}>
        <Probe />
      </QueryProvider>,
    );
    act(() => notifyDealsChanged());
    expect(client.getQueryState(forecastKey)?.isInvalidated).toBe(true);
    expect(client.getQueryState(dealsKey)?.isInvalidated).toBe(true);
    expect(client.getQueryState(otherKey)?.isInvalidated).toBe(false);
    // Invalidated, not dropped: cached figures stay on screen while they refetch.
    expect(client.getQueryData(forecastKey)).toEqual({ cached: true });
  });
});
