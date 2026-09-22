import { beforeEach, describe, expect, it, vi } from "vitest";

import { getApprovals } from "@/lib/api/approvals";

describe("Approvals API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("flowpilot.access_token", "approvals-token");
  });

  it("lists approvals with encoded query parameters", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], limit: 20, offset: 0, total: 0 }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await getApprovals({
      q: "Acme / co",
      status: "pending",
      limit: 20,
      offset: 40,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/approvals?q=Acme+%2F+co&status=pending&limit=20&offset=40",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer approvals-token",
        }),
      }),
    );
  });

  it("omits empty query params", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], limit: 20, offset: 0, total: 0 }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await getApprovals();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/approvals",
      expect.any(Object),
    );
  });
});
