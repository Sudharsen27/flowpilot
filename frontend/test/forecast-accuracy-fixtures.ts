import type {
  ForecastAccuracy,
  ForecastAccuracyBasis,
  ForecastAccuracyComparison,
  ForecastAccuracyLead,
  ForecastAccuracyMonth,
  ForecastAccuracySummary,
} from "@/types/api";

/**
 * A forecast accuracy response as the API returns it, for 2026-08..2026-11 with
 * November in progress (as of 2 November 2026):
 * - August: tracking had not started at any lead.
 * - September: compared at month start; no snapshot in the window at 30 days.
 * - October: compared at month start with no revenue won; a USD snapshot at 30 days.
 * - November: in progress, not scored.
 */

const BASES: ForecastAccuracyBasis[] = ["PROJECTED", "COMMIT_SCENARIO", "BEST_CASE_SCENARIO"];
type Figures = [forecast: string, variance: string | null, variancePercent: string | null, accuracy: string | null];

function comparisons(
  figures: Record<ForecastAccuracyBasis, Figures>,
  status: ForecastAccuracyComparison["accuracy_status"],
): ForecastAccuracyComparison[] {
  return BASES.map((basis) => {
    const [forecast_amount, variance_amount, variance_percent, accuracy_percent] = figures[basis];
    return { basis, forecast_amount, variance_amount, variance_percent, accuracy_percent, accuracy_status: status };
  });
}

function cutoff(periodStart: string, lead: number): { cutoff_at: string; window_start_at: string } {
  const start = Date.parse(`${periodStart}T00:00:00Z`);
  const day = 86_400_000;
  const iso = (ms: number) => new Date(ms).toISOString().replace(".000Z", "Z");
  return { cutoff_at: iso(start - lead * day), window_start_at: iso(start - (lead + 7) * day) };
}

function lead(
  periodStart: string,
  lead_days: number,
  overrides: Partial<ForecastAccuracyLead> = {},
): ForecastAccuracyLead {
  return {
    lead_days,
    ...cutoff(periodStart, lead_days),
    cutoff_rule: lead_days === 0 ? "BEFORE" : "ON_OR_BEFORE",
    snapshot_status: "BEFORE_FIRST_SNAPSHOT",
    snapshot_date: null,
    captured_at: null,
    comparisons: [],
    ...overrides,
  };
}

function month(
  periodStart: string,
  periodEnd: string,
  actual: [count: number, total: string],
  leads: Partial<Record<number, Partial<ForecastAccuracyLead>>>,
  status: ForecastAccuracyMonth["status"] = "CLOSED",
): ForecastAccuracyMonth {
  return {
    label: periodStart.slice(0, 7),
    period_start: periodStart,
    period_end: periodEnd,
    status,
    actual: { count: actual[0], total_amount: actual[1] },
    forecasts: [0, 30, 60, 90].map((days) => lead(periodStart, days, leads[days])),
  };
}

function available(capturedAt: string, list: ForecastAccuracyComparison[]): Partial<ForecastAccuracyLead> {
  return {
    snapshot_status: "AVAILABLE",
    snapshot_date: capturedAt.slice(0, 10),
    captured_at: capturedAt,
    comparisons: list,
  };
}

export const ACCURACY_MONTHS: ForecastAccuracyMonth[] = [
  month("2026-08-01", "2026-08-31", [2, "150000.00"], {}),
  month("2026-09-01", "2026-09-30", [1, "100000.00"], {
    0: available(
      "2026-08-31T00:05:00Z",
      comparisons(
        {
          PROJECTED: ["120000.00", "-20000.00", "-16.7", "80.0"],
          COMMIT_SCENARIO: ["100000.00", "0.00", "0.0", "100.0"],
          BEST_CASE_SCENARIO: ["300000.00", "-200000.00", "-66.7", "-100.0"],
        },
        "COMPUTED",
      ),
    ),
    30: { snapshot_status: "MISSING" },
  }),
  month("2026-10-01", "2026-10-31", [0, "0.00"], {
    0: available(
      "2026-09-30T00:05:00Z",
      comparisons(
        {
          PROJECTED: ["0.00", "0.00", null, null],
          COMMIT_SCENARIO: ["5000.00", "-5000.00", "-100.0", null],
          BEST_CASE_SCENARIO: ["10000.00", "-10000.00", "-100.0", null],
        },
        "NO_ACTUAL_REVENUE",
      ),
    ),
    30: {
      snapshot_status: "CURRENCY_MISMATCH",
      snapshot_date: "2026-09-01",
      captured_at: "2026-09-01T00:05:00Z",
    },
  }),
  month(
    "2026-11-01",
    "2026-11-30",
    [1, "1000001234567.88"],
    {
      0: available(
        "2026-10-31T00:05:00Z",
        comparisons(
          {
            PROJECTED: ["250000.00", null, null, null],
            COMMIT_SCENARIO: ["200000.00", null, null, null],
            BEST_CASE_SCENARIO: ["400000.00", null, null, null],
          },
          "MONTH_IN_PROGRESS",
        ),
      ),
    },
    "IN_PROGRESS",
  ),
];

function summary(
  lead_days: number,
  basis: ForecastAccuracyBasis,
  overrides: Partial<ForecastAccuracySummary> = {},
): ForecastAccuracySummary {
  return {
    lead_days,
    basis,
    months_compared: 0,
    months_missing: 3,
    forecast_total: null,
    actual_total: null,
    variance_amount: null,
    variance_percent: null,
    weighted_accuracy_percent: null,
    status: "NO_COMPARABLE_MONTHS",
    ...overrides,
  };
}

const LEAD_0: Record<ForecastAccuracyBasis, Partial<ForecastAccuracySummary>> = {
  PROJECTED: {
    forecast_total: "120000.00",
    variance_amount: "-20000.00",
    variance_percent: "-16.7",
    weighted_accuracy_percent: "80.0",
  },
  COMMIT_SCENARIO: {
    forecast_total: "105000.00",
    variance_amount: "-5000.00",
    variance_percent: "-4.8",
    weighted_accuracy_percent: "95.0",
  },
  BEST_CASE_SCENARIO: {
    forecast_total: "310000.00",
    variance_amount: "-210000.00",
    variance_percent: "-67.7",
    weighted_accuracy_percent: "-110.0",
  },
};

export const ACCURACY_SUMMARY: ForecastAccuracySummary[] = [0, 30, 60, 90].flatMap((days) =>
  BASES.map((basis) =>
    days === 0
      ? summary(days, basis, {
          months_compared: 2,
          months_missing: 1,
          actual_total: "100000.00",
          status: "COMPUTED",
          ...LEAD_0[basis],
        })
      : summary(days, basis),
  ),
);

export function accuracyFixture(overrides: Partial<ForecastAccuracy> = {}): ForecastAccuracy {
  return {
    currency: "INR",
    as_of: "2026-11-02T06:30:00Z",
    granularity: "month",
    method: "SNAPSHOT_VS_ACTUAL_WON",
    rounding: "PER_DEAL_HALF_UP_CENTS",
    accuracy_formula: "ONE_MINUS_ABS_ERROR_OVER_ACTUAL",
    percent_rounding: "HALF_AWAY_FROM_ZERO_TENTHS",
    variance_sign: "ACTUAL_MINUS_FORECAST",
    from_month: "2026-08-01",
    to_month: "2026-11-01",
    lead_days: [0, 30, 60, 90],
    snapshot_tolerance_days: 7,
    first_captured_at: "2026-08-25T00:05:00Z",
    months: ACCURACY_MONTHS,
    summary: ACCURACY_SUMMARY,
    assumptions: [
      { code: "SNAPSHOT_FIGURES", detail: "Forecast figures are read from saved snapshots." },
      { code: "UTC_MONTHS", detail: "Months are UTC calendar months." },
    ],
    ...overrides,
  };
}
