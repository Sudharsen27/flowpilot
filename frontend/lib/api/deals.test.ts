import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";
import {
  changeDealStage,
  createDeal,
  getDealHistory,
  isRevisionConflict,
  listDeals,
  updateDeal,
  validationErrors,
} from "@/lib/api/deals";
import { listSalesTargets, upsertSalesTarget } from "@/lib/api/sales-targets";

function mockFetch(body: unknown = {}, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  );
}

describe("deals API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("flowpilot.access_token", "deal-token");
  });

  it("lists deals with backend filter names and clamped paging", async () => {
    const fetchMock = mockFetch({ items: [], limit: 20, offset: 0, total: 0 });
    await listDeals({
      stage: "PROPOSAL",
      ownerUserId: "user/1",
      closeDateFrom: "2026-11-01",
      closeDateTo: "2026-12-31",
      q: "  acme  ",
      limit: 500,
      offset: -4,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/deals?stage=PROPOSAL&owner_user_id=user%2F1&close_date_from=2026-11-01&close_date_to=2026-12-31&q=acme&limit=100&offset=0",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer deal-token" }),
      }),
    );
  });

  it("sends amounts as strings and writes to the documented endpoints", async () => {
    const fetchMock = mockFetch({});
    await createDeal({ name: "Acme", amount: "125000.50", expected_close_date: "2026-12-15" });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8000/api/v1/deals");
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      name: "Acme",
      amount: "125000.50",
      expected_close_date: "2026-12-15",
    });
    await updateDeal("deal/1", { expected_revision: 2, amount: "10.00" });
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/api/v1/deals/deal%2F1");
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: "PATCH" });
    await changeDealStage("deal-1", { stage: "PROPOSAL", expected_revision: 3 });
    expect(fetchMock.mock.calls[2]?.[0]).toBe("http://localhost:8000/api/v1/deals/deal-1/stage");
    await getDealHistory("deal-1", { limit: 500 });
    expect(fetchMock.mock.calls[3]?.[0]).toBe(
      "http://localhost:8000/api/v1/deals/deal-1/history?limit=200",
    );
  });

  it("calls the sales target endpoints with PUT for upserts", async () => {
    const fetchMock = mockFetch({});
    await listSalesTargets({ organizationOnly: true, periodFrom: "2026-01-01", limit: 999 });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8000/api/v1/sales-targets?organization_only=true&period_from=2026-01-01&limit=200",
    );
    await upsertSalesTarget({ period_start: "2026-11-01", amount: "500000.00" });
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: "PUT",
      body: JSON.stringify({ period_start: "2026-11-01", amount: "500000.00" }),
    });
  });

  it("recognizes revision conflicts and maps validation errors to fields", () => {
    expect(isRevisionConflict(new ApiError("x", 409, { current_revision: 3 }))).toBe(true);
    expect(isRevisionConflict(new ApiError("x", 422))).toBe(false);
    expect(
      validationErrors(
        new ApiError("x", 422, {
          detail: [
            { loc: ["body", "amount"], msg: "Value error, Send amounts as a string" },
            { loc: ["body"], msg: "Something general" },
          ],
        }),
      ),
    ).toEqual({ amount: "Send amounts as a string", form: "Something general" });
    expect(
      validationErrors(new ApiError("x", 422, { detail: "Lost deals require a lost reason" })),
    ).toEqual({ form: "Lost deals require a lost reason" });
    expect(validationErrors(new ApiError("x", 500))).toEqual({});
  });
});
