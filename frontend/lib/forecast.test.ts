import { describe, expect, it } from "vitest";

import {
  FORECAST_STALE_TIME_MS,
  forecastQueryKey,
  formatForecastPeriod,
  formatForecastPeriodShort,
  forecastMethodLabel,
  forecastPeriodOptions,
  forecastRoundingLabel,
  hasForecastTargets,
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

describe("forecast target support", () => {
  const target = {
    status: "NONE" as const,
    amount: null,
    months_in_range: 1,
    months_with_target: 0,
    missing_months: ["2026-11-01"],
    has_owner_targets: false,
    comparisons: [],
  };
  const zeroOpen = { count: 0, total_amount: "0.00", weighted_amount: "0.00", override_count: 0 };
  const period = {
    label: "2026-11",
    period_start: "2026-11-01",
    period_end: "2026-11-30",
    won: { count: 0, total_amount: "0.00" },
    open: zeroOpen,
    projected_amount: "0.00",
    commit_scenario_amount: "0.00",
    best_case_scenario_amount: "0.00",
    target,
  };
  const forecast = {
    currency: "INR",
    as_of: "2026-11-02T00:00:00Z",
    granularity: "month" as const,
    method: "STAGE_PROBABILITY_WEIGHTED" as const,
    rounding: "PER_DEAL_HALF_UP_CENTS" as const,
    horizon_start: "2026-11-01",
    horizon_end: "2026-11-30",
    periods: [period],
    past_due: { ...zeroOpen, oldest_expected_close_date: null },
    beyond_horizon: zeroOpen,
    open_pipeline: zeroOpen,
    won_in_horizon: { count: 0, total_amount: "0.00" },
    projected_in_horizon_amount: "0.00",
    target_in_horizon: target,
    stage_probabilities: [],
    assumptions: [],
    excluded_other_currency_count: 0,
  };

  it("is true only when the horizon and every period carry target figures", () => {
    expect(hasForecastTargets(forecast)).toBe(true);
    expect(hasForecastTargets({ ...forecast, target_in_horizon: undefined })).toBe(false);
    expect(hasForecastTargets({ ...forecast, periods: [{ ...period, target: undefined }] })).toBe(false);
    expect(
      hasForecastTargets({ ...forecast, periods: [{ ...period, commit_scenario_amount: undefined }] }),
    ).toBe(false);
  });
});
