import { describe, expect, it } from "vitest";

import { parseSalesTargetsYear, salesTargetsHref } from "@/lib/sales-targets";

const parse = (query: string) => parseSalesTargetsYear(new URLSearchParams(query), 2026);

describe("sales targets URL state", () => {
  it("reads a four-digit year from the URL", () => {
    expect(parse("year=2027")).toBe(2027);
    expect(parse("year=%202031%20")).toBe(2031);
  });

  it("falls back for a missing, malformed or implausible year", () => {
    for (const query of ["", "year=", "year=abc", "year=27", "year=20271", "year=-2027", "year=1899"]) {
      expect(parse(query)).toBe(2026);
    }
  });

  it("links to the year of a date-only string", () => {
    expect(salesTargetsHref("2027-02-01")).toBe("/deals/targets?year=2027");
    expect(salesTargetsHref("bad")).toBe("/deals/targets");
  });
});
