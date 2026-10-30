import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ForecastTargets } from "@/components/forecast/forecast-targets";
import type {
  ForecastPeriod,
  ForecastTarget,
  ForecastTargetComparison,
  PipelineForecast,
} from "@/types/api";

const zeroOpen = {
  count: 0,
  total_amount: "0.00",
  weighted_amount: "0.00",
  override_count: 0,
  category_totals: [],
};

/** Comparisons in the API's order; [amount, percent, remaining, above] per basis. */
function comparisons(
  rows: [string, string | null, string, string][],
): ForecastTargetComparison[] {
  const bases = ["WON", "COMMIT_SCENARIO", "BEST_CASE_SCENARIO", "PROJECTED"] as const;
  return rows.map(([amount, attainment_percent, remaining_amount, above_target_amount], index) => ({
    basis: bases[index],
    amount,
    attainment_percent,
    remaining_amount,
    above_target_amount,
  }));
}

function target(overrides: Partial<ForecastTarget> = {}): ForecastTarget {
  return {
    status: "NONE",
    amount: null,
    months_in_range: 3,
    months_with_target: 0,
    missing_months: ["2026-10-01", "2026-11-01", "2026-12-01"],
    has_owner_targets: false,
    comparisons: [],
    ...overrides,
  };
}

const fullQ4 = target({
  status: "FULL",
  amount: "600000.00",
  months_with_target: 3,
  missing_months: [],
  comparisons: comparisons([
    ["150000.00", "25.0", "450000.00", "0.00"],
    ["450000.00", "75.0", "150000.00", "0.00"],
    ["600000.00", "100.0", "0.00", "0.00"],
    ["720000.33", "120.1", "0.00", "120000.33"],
  ]),
});

const partialQ1 = target({
  amount: "50000.00",
  status: "PARTIAL",
  months_with_target: 1,
  missing_months: ["2027-02-01", "2027-03-01"],
});

function period(overrides: Partial<ForecastPeriod> & Pick<ForecastPeriod, "label" | "period_start" | "period_end">): ForecastPeriod {
  return {
    won: { count: 0, total_amount: "0.00" },
    open: zeroOpen,
    projected_amount: "0.00",
    commit_scenario_amount: "0.00",
    best_case_scenario_amount: "0.00",
    target: target(),
    ...overrides,
  };
}

function forecast(overrides: Partial<PipelineForecast> = {}): PipelineForecast {
  return {
    currency: "INR",
    as_of: "2026-10-29T06:30:00Z",
    granularity: "quarter",
    method: "STAGE_PROBABILITY_WEIGHTED",
    rounding: "PER_DEAL_HALF_UP_CENTS",
    horizon_start: "2026-10-01",
    horizon_end: "2027-03-31",
    periods: [
      period({
        label: "2026-Q4",
        period_start: "2026-10-01",
        period_end: "2026-12-31",
        won: { count: 1, total_amount: "150000.00" },
        commit_scenario_amount: "450000.00",
        best_case_scenario_amount: "600000.00",
        projected_amount: "720000.33",
        target: fullQ4,
      }),
      period({
        label: "2027-Q1",
        period_start: "2027-01-01",
        period_end: "2027-03-31",
        commit_scenario_amount: "80000.00",
        best_case_scenario_amount: "90000.00",
        projected_amount: "40000.00",
        target: partialQ1,
      }),
    ],
    past_due: { ...zeroOpen, oldest_expected_close_date: null },
    beyond_horizon: zeroOpen,
    open_pipeline: zeroOpen,
    won_in_horizon: { count: 1, total_amount: "150000.00" },
    projected_in_horizon_amount: "760000.33",
    target_in_horizon: target({
      status: "FULL",
      amount: "1200000.00",
      months_in_range: 6,
      months_with_target: 6,
      missing_months: [],
      comparisons: comparisons([
        ["150000.00", "12.5", "1050000.00", "0.00"],
        ["530000.00", "44.2", "670000.00", "0.00"],
        ["690000.00", "57.5", "510000.00", "0.00"],
        ["760000.33", "63.4", "439999.67", "0.00"],
      ]),
    }),
    stage_probabilities: [],
    assumptions: [],
    excluded_other_currency_count: 0,
    ...overrides,
  };
}

function renderTargets(data: PipelineForecast, canManageTargets = true) {
  return render(<ForecastTargets forecast={data} canManageTargets={canManageTargets} />);
}

function horizonCard() {
  return screen.getByRole("region", { name: "Target for this horizon" });
}

function periodRow(name: string) {
  return screen.getByRole("row", { name: new RegExp(`^${name}`) });
}

describe("ForecastTargets", () => {
  it("shows the full horizon target with the API's percentages and gaps", () => {
    renderTargets(forecast());
    const card = horizonCard();
    expect(within(card).getByText("₹12,00,000.00")).toBeInTheDocument();
    expect(within(card).getByText("Organization target")).toBeInTheDocument();
    const items = within(card).getAllByRole("listitem");
    expect(items.map((item) => item.getAttribute("data-basis"))).toEqual([
      "WON",
      "COMMIT_SCENARIO",
      "BEST_CASE_SCENARIO",
      "PROJECTED",
    ]);
    expect(items[0]).toHaveTextContent("Won to date (actual)");
    expect(items[0]).toHaveTextContent("₹1,50,000.00");
    expect(items[0]).toHaveTextContent("12.5% of target");
    expect(items[0]).toHaveTextContent("₹10,50,000.00 to go");
    expect(items[3]).toHaveTextContent("Projected (estimate)");
    expect(items[3]).toHaveTextContent("63.4% of target");
    expect(items[3]).toHaveTextContent("₹4,39,999.67 to go");
    expect(within(card).queryByRole("link", { name: "Set targets" })).not.toBeInTheDocument();
  });

  it("sizes progress bars from the API percentage, capped at the target, and hides them from assistive tech", () => {
    renderTargets(
      forecast({
        target_in_horizon: fullQ4,
      }),
    );
    const bars = within(horizonCard()).getAllByTestId("target-progress");
    expect(bars.map((bar) => bar.style.width)).toEqual(["25%", "75%", "100%", "100%"]);
    for (const bar of bars) expect(bar.parentElement).toHaveAttribute("aria-hidden", "true");
    const items = within(horizonCard()).getAllByRole("listitem");
    expect(items[2]).toHaveTextContent("On target");
    expect(items[3]).toHaveTextContent("120.1% of target");
    expect(items[3]).toHaveTextContent("Above target by ₹1,20,000.33");
  });

  it("shows every period with its target status and per-period figures", () => {
    renderTargets(forecast());
    const q4 = periodRow("Q4 2026");
    expect(q4).toHaveTextContent("₹6,00,000.00");
    expect(q4).toHaveTextContent("25.0% of target");
    expect(q4).toHaveTextContent("₹4,50,000.00");
    expect(q4).toHaveTextContent("75.0% of target");
    expect(q4).toHaveTextContent("120.1% of target");

    const q1 = periodRow("Q1 2027");
    expect(q1).toHaveTextContent("₹50,000.00");
    expect(q1).toHaveTextContent("Partial: 1 of 3 months");
    // Figures still show; attainment does not.
    expect(q1).toHaveTextContent("₹80,000.00");
    expect(q1).toHaveTextContent("₹90,000.00");
    expect(q1).not.toHaveTextContent("% of target");
  });

  it("shows a partial horizon target with its missing months and no attainment", () => {
    renderTargets(
      forecast({
        target_in_horizon: target({
          status: "PARTIAL",
          amount: "650000.00",
          months_in_range: 6,
          months_with_target: 4,
          missing_months: ["2027-02-01", "2027-03-01"],
        }),
      }),
    );
    const card = horizonCard();
    expect(card).toHaveAttribute("data-status", "PARTIAL");
    expect(within(card).getByText("₹6,50,000.00")).toBeInTheDocument();
    expect(within(card).getByText("Partial target (months set so far)")).toBeInTheDocument();
    expect(within(card).getByText("Target incomplete: 4 of 6 months set")).toBeInTheDocument();
    expect(card).toHaveTextContent("Missing: February 2027, March 2027.");
    expect(card).toHaveTextContent("Attainment is shown once every month has a target.");
    expect(card).not.toHaveTextContent("% of target");
    expect(within(card).queryAllByTestId("target-progress")).toHaveLength(0);
    expect(within(card).getByRole("link", { name: "Set targets" })).toHaveAttribute(
      "href",
      "/deals/targets?year=2027",
    );
    expect(
      screen.getByText("Percentages appear only for periods where every month has an organization target."),
    ).toBeInTheDocument();
  });

  it("counts missing months beyond the first six", () => {
    const months = Array.from({ length: 9 }, (_, index) => `2027-${String(index + 1).padStart(2, "0")}-01`);
    renderTargets(
      forecast({
        target_in_horizon: target({
          status: "PARTIAL",
          amount: "1.00",
          months_in_range: 10,
          months_with_target: 1,
          missing_months: months,
        }),
      }),
    );
    expect(horizonCard()).toHaveTextContent(
      "Missing: January 2027, February 2027, March 2027, April 2027, May 2027, June 2027 and 3 more.",
    );
  });

  it("never shows a zero or a percentage when no target is set", () => {
    renderTargets(forecast({ target_in_horizon: target({ months_in_range: 6, missing_months: ["2026-10-01"] }) }));
    const card = horizonCard();
    expect(card).toHaveAttribute("data-status", "NONE");
    expect(within(card).getByText("No organization target set")).toBeInTheDocument();
    expect(card).toHaveTextContent("None of the 6 months has an organization target.");
    expect(card).not.toHaveTextContent("₹0.00");
    expect(card).not.toHaveTextContent("%");
    expect(within(card).getByRole("link", { name: "Set targets" })).toHaveAttribute(
      "href",
      "/deals/targets?year=2026",
    );
  });

  it("hints at owner targets without adding them in", () => {
    renderTargets(
      forecast({
        periods: [
          period({
            label: "2026-Q4",
            period_start: "2026-10-01",
            period_end: "2026-12-31",
            target: target({ has_owner_targets: true }),
          }),
        ],
        target_in_horizon: target({ has_owner_targets: true }),
      }),
    );
    const card = horizonCard();
    expect(within(card).getByText("No organization target set")).toBeInTheDocument();
    expect(within(card).getByRole("note")).toHaveTextContent(
      "Owner targets exist for this horizon, but they are set per person and are not added together into an organization target.",
    );
    expect(periodRow("Q4 2026")).toHaveTextContent("Not setOwner targets only");
  });

  it("does not show the owner hint when no owner targets exist", () => {
    renderTargets(forecast({ target_in_horizon: target() }));
    expect(within(horizonCard()).queryByRole("note")).not.toBeInTheDocument();
  });

  it("hides Set targets from members", () => {
    renderTargets(forecast({ target_in_horizon: target() }), false);
    const card = horizonCard();
    expect(within(card).queryByRole("link", { name: "Set targets" })).not.toBeInTheDocument();
    expect(card).toHaveTextContent("Owners and admins can set organization targets.");
  });

  it("shows a zero target without a percentage", () => {
    const zeroTarget = target({
      status: "FULL",
      amount: "0.00",
      months_in_range: 1,
      months_with_target: 1,
      missing_months: [],
      comparisons: comparisons([
        ["100.00", null, "0.00", "100.00"],
        ["0.00", null, "0.00", "0.00"],
        ["100.00", null, "0.00", "100.00"],
        ["100.00", null, "0.00", "100.00"],
      ]),
    });
    renderTargets(forecast({ target_in_horizon: zeroTarget }));
    const card = horizonCard();
    // The target itself and the zero Commit figure.
    expect(within(card).getAllByText("₹0.00")).toHaveLength(2);
    expect(within(card).getByText("Organization target")).toBeInTheDocument();
    expect(card).not.toHaveTextContent("% of target");
    const items = within(card).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Target is 0");
    expect(items[0]).toHaveTextContent("Above target by ₹100.00");
    expect(items[1]).toHaveTextContent("On target");
    const bars = within(card).getAllByTestId("target-progress");
    expect(bars.map((bar) => bar.style.width)).toEqual(["100%", "0%", "100%", "100%"]);
  });

  it("explains when an older API returns no target figures", () => {
    const current = forecast();
    renderTargets({
      ...current,
      target_in_horizon: undefined,
      periods: current.periods.map((item) => ({ ...item, target: undefined })),
    });
    expect(screen.getByText("Target comparison unavailable")).toBeInTheDocument();
    expect(screen.queryByText("No organization target set")).not.toBeInTheDocument();
  });

  it("describes month targets in the month view", () => {
    renderTargets(forecast({ granularity: "month" }));
    expect(
      screen.getByText(/a month's target is compared with that month/),
    ).toBeInTheDocument();
  });
});
