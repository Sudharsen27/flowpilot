import { render, screen } from "@testing-library/react";
import { useQueryClient } from "@tanstack/react-query";
import { act } from "react";
import { describe, expect, it } from "vitest";

import { QueryProvider } from "@/components/providers/query-provider";
import { clearAccessToken } from "@/lib/auth/storage";
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
});
