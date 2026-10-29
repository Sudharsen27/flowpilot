import { describe, expect, it } from "vitest";

import {
  FORECAST_STALE_TIME_MS,
  forecastQueryKey,
  formatForecastPeriod,
  formatForecastPeriodShort,
  forecastMethodLabel,
  forecastPeriodOptions,
  forecastRoundingLabel,
  parseForecastSearchParams,
  serializeForecastSearchParams,
} from "@/lib/forecast";

const parse = (query: string) => parseForecastSearchParams(new URLSearchParams(query));

describe("forecast URL state", () => {
  it("defaults to 4 quarters", () => {
    expect(parse("")).toEqual({ granularity: "quarter", periods: 4 });
  });

  it("defaults months to 12 periods", () => {
    expect(parse("granularity=month")).toEqual({ granularity: "month", periods: 12 });
  });

  it("accepts periods within the backend limits", () => {
    expect(parse("granularity=month&periods=24")).toEqual({ granularity: "month", periods: 24 });
    expect(parse("periods=8")).toEqual({ granularity: "quarter", periods: 8 });
    expect(parse("periods=1")).toEqual({ granularity: "quarter", periods: 1 });
  });

  it("falls back to the default for out-of-range or malformed values", () => {
    expect(parse("periods=9").periods).toBe(4);
    expect(parse("granularity=month&periods=25").periods).toBe(12);
    expect(parse("periods=0").periods).toBe(4);
    expect(parse("periods=2.5").periods).toBe(4);
    expect(parse("periods=-3").periods).toBe(4);
    expect(parse("granularity=week").granularity).toBe("quarter");
  });

  it("omits defaults so /forecast stays canonical", () => {
    expect(serializeForecastSearchParams({ granularity: "quarter", periods: 4 })).toBe("");
    expect(serializeForecastSearchParams({ granularity: "month", periods: 12 })).toBe("granularity=month");
    expect(serializeForecastSearchParams({ granularity: "quarter", periods: 8 })).toBe("periods=8");
    expect(serializeForecastSearchParams({ granularity: "month", periods: 6 })).toBe(
      "granularity=month&periods=6",
    );
  });

  it("offers horizon choices including a valid URL value", () => {
    expect(forecastPeriodOptions("quarter", 4)).toEqual([2, 4, 6, 8]);
    expect(forecastPeriodOptions("month", 7)).toEqual([3, 6, 7, 12, 18, 24]);
  });
});

describe("forecast labels", () => {
  it("formats API period labels", () => {
    const quarter = { label: "2026-Q4", period_start: "2026-10-01" };
    const month = { label: "2026-11", period_start: "2026-11-01" };
    expect(formatForecastPeriod(quarter, "quarter")).toBe("Q4 2026");
    expect(formatForecastPeriodShort(quarter, "quarter")).toBe("Q4 2026");
    expect(formatForecastPeriod(month, "month")).toBe("November 2026");
    expect(formatForecastPeriodShort(month, "month")).toBe("Nov 26");
  });

  it("shows unknown method and rounding codes as returned", () => {
    expect(forecastMethodLabel("STAGE_PROBABILITY_WEIGHTED")).toBe("Stage-probability weighted");
    expect(forecastMethodLabel("SOMETHING_NEW")).toBe("SOMETHING_NEW");
    expect(forecastRoundingLabel("PER_DEAL_HALF_UP_CENTS")).toMatch(/rounded half-up to the cent/);
    expect(forecastRoundingLabel("BANKERS")).toBe("BANKERS");
  });
});

describe("forecast query key", () => {
  it("is scoped to the organization and the exact horizon", () => {
    expect(forecastQueryKey("org-1", { granularity: "quarter", periods: 4 })).toEqual([
      "pipeline-forecast",
      "org-1",
      { granularity: "quarter", periods: 4 },
    ]);
    const keys = [
      forecastQueryKey("org-1", { granularity: "quarter", periods: 4 }),
      forecastQueryKey("org-1", { granularity: "month", periods: 4 }),
      forecastQueryKey("org-1", { granularity: "quarter", periods: 8 }),
      forecastQueryKey("org-2", { granularity: "quarter", periods: 4 }),
    ].map((key) => JSON.stringify(key));
    expect(new Set(keys).size).toBe(4);
  });

  it("keeps forecast data fresh for one minute", () => {
    expect(FORECAST_STALE_TIME_MS).toBe(60_000);
  });
});
