import { describe, expect, it } from "vitest";

import {
  DEFAULT_ACCURACY_STATE,
  accuracyBasisLabel,
  accuracyMonthRange,
  formatAccuracyPercent,
  formatSignedMoney,
  formatSignedPercent,
  forecastAccuracyQueryKey,
  parseForecastAccuracySearchParams,
  serializeForecastAccuracySearchParams,
  snapshotStatusText,
  type ForecastAccuracyUrlState,
} from "@/lib/forecast-accuracy";

const parse = (search: string) => parseForecastAccuracySearchParams(new URLSearchParams(search));
const state = (overrides: Partial<ForecastAccuracyUrlState>) => ({ ...DEFAULT_ACCURACY_STATE, ...overrides });

describe("forecast accuracy URL state", () => {
  it("defaults to 6 closed months, lead 0 and the projected basis", () => {
    expect(parse("")).toEqual({ range: 6, includeCurrent: false, lead: 0, basis: "PROJECTED" });
  });

  it("reads every supported value", () => {
    expect(parse("range=24&current=1&lead=90&basis=best_case_scenario")).toEqual({
      range: 24,
      includeCurrent: true,
      lead: 90,
      basis: "BEST_CASE_SCENARIO",
    });
  });

  it.each(["range=5", "range=abc", "lead=45", "lead=-30", "basis=WON", "current=yes"])(
    "falls back to the default for %s",
    (search) => {
      expect(parse(search)).toEqual(DEFAULT_ACCURACY_STATE);
    },
  );

  it("omits defaults and round-trips the rest", () => {
    expect(serializeForecastAccuracySearchParams(DEFAULT_ACCURACY_STATE)).toBe("");
    const custom = state({ range: 12, includeCurrent: true, lead: 30, basis: "COMMIT_SCENARIO" });
    const serialized = serializeForecastAccuracySearchParams(custom);
    expect(serialized).toBe("range=12&current=1&lead=30&basis=COMMIT_SCENARIO");
    expect(parse(serialized)).toEqual(custom);
  });
});

describe("accuracyMonthRange", () => {
  const now = new Date("2026-11-02T06:30:00Z");

  it("sends no months for the default range, so the server's clock decides", () => {
    expect(accuracyMonthRange(DEFAULT_ACCURACY_STATE, now)).toEqual({ fromMonth: null, toMonth: null });
  });

  it("ends with the last closed UTC month", () => {
    expect(accuracyMonthRange(state({ range: 3 }), now)).toEqual({
      fromMonth: "2026-08-01",
      toMonth: "2026-10-01",
    });
  });

  it("adds the current month on top of the closed months", () => {
    expect(accuracyMonthRange(state({ includeCurrent: true }), now)).toEqual({
      fromMonth: "2026-05-01",
      toMonth: "2026-11-01",
    });
  });

  it("crosses the year boundary", () => {
    expect(accuracyMonthRange(state({ range: 12 }), new Date("2027-01-15T00:00:00Z"))).toEqual({
      fromMonth: "2026-01-01",
      toMonth: "2026-12-01",
    });
  });

  it("uses the UTC month, not the local one", () => {
    // 05:00 on 1 December in UTC+5:30 is still 30 November in UTC.
    expect(accuracyMonthRange(state({ range: 3 }), new Date("2026-11-30T23:30:00Z"))).toEqual({
      fromMonth: "2026-08-01",
      toMonth: "2026-10-01",
    });
  });

  it("never asks for more than 24 months", () => {
    expect(accuracyMonthRange(state({ range: 24, includeCurrent: true }), now)).toEqual({
      fromMonth: "2024-12-01",
      toMonth: "2026-11-01",
    });
  });

  it("keys the cache by organization and months", () => {
    expect(forecastAccuracyQueryKey("org-1", { fromMonth: null, toMonth: null })).toEqual([
      "pipeline-forecast-accuracy",
      "org-1",
      { fromMonth: null, toMonth: null },
    ]);
  });
});

describe("forecast accuracy labels", () => {
  it.each([
    ["AVAILABLE", null],
    ["MISSING", "No snapshot in the 7 days before the cutoff"],
    ["BEFORE_FIRST_SNAPSHOT", "Before forecast tracking started"],
    ["CURRENCY_MISMATCH", "Saved in another currency; not compared"],
    ["SOMETHING_NEW", "SOMETHING_NEW"],
  ])("explains snapshot status %s", (status, text) => {
    expect(snapshotStatusText(status, 7)).toBe(text);
  });

  it("falls back to the raw basis code", () => {
    expect(accuracyBasisLabel("COMMIT_SCENARIO")).toBe("Commit scenario");
    expect(accuracyBasisLabel("NEW_BASIS")).toBe("NEW_BASIS");
  });
});

describe("signed figures", () => {
  it("formats variance percentages with an explicit sign and keeps null", () => {
    expect(formatSignedPercent("12.5")).toBe("+12.5%");
    expect(formatSignedPercent("-3.0")).toBe("\u22123.0%");
    expect(formatSignedPercent("0.0")).toBe("0.0%");
    expect(formatSignedPercent(null)).toBeNull();
  });

  it("shows accuracy as returned, negative values included", () => {
    expect(formatAccuracyPercent("83.7")).toBe("83.7%");
    expect(formatAccuracyPercent("-9800.0")).toBe("\u22129800.0%");
    expect(formatAccuracyPercent(null)).toBeNull();
  });

  it("formats variance money exactly, with a sign", () => {
    expect(formatSignedMoney("1000001234567.88", "INR")).toBe("+₹10,00,00,12,34,567.88");
    expect(formatSignedMoney("-495.00", "INR")).toBe("\u2212₹495.00");
    expect(formatSignedMoney("0.00", "INR")).toBe("₹0.00");
    expect(formatSignedMoney(null, "INR")).toBeNull();
  });
});
