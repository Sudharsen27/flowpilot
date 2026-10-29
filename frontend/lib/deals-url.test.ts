import { describe, expect, it } from "vitest";

import {
  buildCreateDealHref,
  buildDealHref,
  hasDealFilters,
  parseDealsSearchParams,
  serializeDealsSearchParams,
} from "@/lib/deals-url";

function parse(query: string) {
  return parseDealsSearchParams(new URLSearchParams(query));
}

describe("deals URL state", () => {
  it("parses every filter and round-trips", () => {
    const state = parse(
      "q=acme&stage=proposal&category=commit&owner=user-1&from=2026-11-01&to=2026-12-31&offset=40",
    );
    expect(state).toEqual({
      q: "acme",
      stage: "PROPOSAL",
      forecastCategory: "COMMIT",
      ownerUserId: "user-1",
      closeDateFrom: "2026-11-01",
      closeDateTo: "2026-12-31",
      offset: 40,
      create: false,
      leadId: null,
    });
    expect(parse(serializeDealsSearchParams(state))).toEqual(state);
    expect(hasDealFilters(state)).toBe(true);
  });

  it("drops invalid values before they reach the API", () => {
    expect(
      parse(
        "stage=WON&category=CLOSED&owner=" + "x".repeat(37) + "&from=2026-02-30&to=soon&offset=-1",
      ),
    ).toMatchObject({
      stage: null,
      forecastCategory: null,
      ownerUserId: null,
      closeDateFrom: null,
      closeDateTo: null,
      offset: 0,
    });
    // A category alone counts as a filter.
    expect(hasDealFilters(parse("category=BEST_CASE"))).toBe(true);
    expect(serializeDealsSearchParams(parse("category=best_case"))).toBe("category=BEST_CASE");
    expect(hasDealFilters(parse(""))).toBe(false);
    expect(serializeDealsSearchParams(parse(""))).toBe("");
  });

  it("builds create-from-lead and detail links", () => {
    expect(buildCreateDealHref("lead-1")).toBe("/deals?create=1&lead_id=lead-1");
    expect(parse("create=1&lead_id=lead-1")).toMatchObject({ create: true, leadId: "lead-1" });
    expect(serializeDealsSearchParams({ ...parse("lead_id=lead-1"), create: false })).toBe("");
    expect(buildDealHref("deal/1")).toBe("/deals/deal%2F1");
  });
});
