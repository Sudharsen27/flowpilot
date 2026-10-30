import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";
import {
  changeDealStage,
  correctWonDealAmount,
  createDeal,
  forbiddenMessage,
  getDealHistory,
  isRevisionConflict,
  listDeals,
  updateDeal,
  validationErrors,
} from "@/lib/api/deals";
import { listSalesTargets, upsertSalesTarget } from "@/lib/api/sales-targets";
import { DEALS_CHANGED_EVENT, SALES_TARGETS_CHANGED_EVENT } from "@/lib/deal-events";

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
      forecastCategory: "COMMIT",
      ownerUserId: "user/1",
      closeDateFrom: "2026-11-01",
      closeDateTo: "2026-12-31",
      q: "  acme  ",
      limit: 500,
      offset: -4,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/deals?stage=PROPOSAL&forecast_category=COMMIT&owner_user_id=user%2F1&close_date_from=2026-11-01&close_date_to=2026-12-31&q=acme&limit=100&offset=0",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer deal-token" }),
      }),
    );
  });

  it("announces every deal write, including failed ones, so cached forecasts refresh", async () => {
    const listener = vi.fn();
    window.addEventListener(DEALS_CHANGED_EVENT, listener);
    try {
      mockFetch({});
      await createDeal({ name: "Acme", amount: "1.00", expected_close_date: "2026-12-15" });
      await updateDeal("deal-1", { expected_revision: 1, amount: "2.00" });
      await changeDealStage("deal-1", { expected_revision: 2, stage: "PROPOSAL" });
      await correctWonDealAmount("deal-1", { expected_revision: 3, amount: "3.00", reason: "Fix" });
      expect(listener).toHaveBeenCalledTimes(4);

      vi.restoreAllMocks();
      mockFetch({ detail: "Deal changed" }, 409);
      await expect(updateDeal("deal-1", { expected_revision: 1, forecast_category: "COMMIT" })).rejects.toMatchObject({
        status: 409,
      });
      expect(listener).toHaveBeenCalledTimes(5);

      // Reads never announce a change.
      mockFetch({ items: [], limit: 20, offset: 0, total: 0 });
      await listDeals();
      expect(listener).toHaveBeenCalledTimes(5);
    } finally {
      window.removeEventListener(DEALS_CHANGED_EVENT, listener);
    }
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

  it("announces every sales target save, including failed ones, but not deal changes", async () => {
    const targetListener = vi.fn();
    const dealListener = vi.fn();
    window.addEventListener(SALES_TARGETS_CHANGED_EVENT, targetListener);
    window.addEventListener(DEALS_CHANGED_EVENT, dealListener);
    try {
      mockFetch({});
      await upsertSalesTarget({ period_start: "2026-11-01", amount: "500000.00" });
      expect(targetListener).toHaveBeenCalledTimes(1);

      vi.restoreAllMocks();
      mockFetch({ detail: "Only owners and admins can set targets" }, 403);
      await expect(
        upsertSalesTarget({ period_start: "2026-11-01", amount: "1.00" }),
      ).rejects.toMatchObject({ status: 403 });
      expect(targetListener).toHaveBeenCalledTimes(2);

      // Reads never announce a change, and target saves are not deal writes.
      mockFetch({ items: [], limit: 50, offset: 0, total: 0 });
      await listSalesTargets();
      expect(targetListener).toHaveBeenCalledTimes(2);
      expect(dealListener).not.toHaveBeenCalled();
    } finally {
      window.removeEventListener(SALES_TARGETS_CHANGED_EVENT, targetListener);
      window.removeEventListener(DEALS_CHANGED_EVENT, dealListener);
    }
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

  it("posts won-amount corrections with the amount as a string and the reason", async () => {
    const fetchMock = mockFetch({});
    await correctWonDealAmount("deal/1", {
      expected_revision: 4,
      amount: "118500.00",
      reason: "Invoice discount",
    });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8000/api/v1/deals/deal%2F1/amount-correction",
    );
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({
        expected_revision: 4,
        amount: "118500.00",
        reason: "Invoice discount",
      }),
    });
  });

  it("returns the API's reason for permission errors only", () => {
    expect(
      forbiddenMessage(
        new ApiError("x", 403, {
          detail: "Only owners and admins can move a won deal to another stage",
        }),
      ),
    ).toBe("Only owners and admins can move a won deal to another stage");
    expect(forbiddenMessage(new ApiError("x", 403, null))).toBe(
      "You do not have permission to make this change.",
    );
    expect(forbiddenMessage(new ApiError("x", 422, { detail: "Nope" }))).toBeNull();
    expect(forbiddenMessage(new Error("network"))).toBeNull();
  });
});
