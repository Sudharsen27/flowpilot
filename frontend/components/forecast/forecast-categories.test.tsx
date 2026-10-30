import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ForecastCategories } from "@/components/forecast/forecast-categories";
import { formatMoneyCompact } from "@/lib/money";
import type {
  ForecastCategory,
  ForecastCategoryTotals,
  ForecastOpenTotals,
  ForecastPeriod,
  PipelineForecast,
} from "@/types/api";

function categories(
  values: Partial<Record<ForecastCategory, [count: number, total: string, weighted: string]>> = {},
): ForecastCategoryTotals[] {
  return (["PIPELINE", "BEST_CASE", "COMMIT"] as const).map((category) => {
    const [count, total_amount, weighted_amount] = values[category] ?? [0, "0.00", "0.00"];
    return { category, count, total_amount, weighted_amount };
  });
}

function open(
  count: number,
  total: string,
  weighted: string,
  values: Parameters<typeof categories>[0] = {},
): ForecastOpenTotals {
  return {
    count,
    total_amount: total,
    weighted_amount: weighted,
    override_count: 0,
    category_totals: categories(values),
  };
}

const zero = open(0, "0.00", "0.00");

function period(label: string, start: string, end: string, totals: ForecastOpenTotals): ForecastPeriod {
  return {
    label,
    period_start: start,
    period_end: end,
    won: { count: 0, total_amount: "0.00" },
    open: totals,
    projected_amount: totals.weighted_amount,
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
      period(
        "2026-Q4",
        "2026-10-01",
        "2026-12-31",
        open(3, "500000.00", "125000.25", {
          PIPELINE: [1, "50000.00", "5000.00"],
          BEST_CASE: [1, "150000.00", "20000.00"],
          COMMIT: [1, "300000.00", "100000.25"],
        }),
      ),
      period("2027-Q1", "2027-01-01", "2027-03-31", zero),
    ],
    past_due: { ...open(1, "7.00", "0.70", { COMMIT: [1, "7.00", "0.70"] }), oldest_expected_close_date: "2026-08-01" },
    beyond_horizon: open(1, "11.00", "1.10", { BEST_CASE: [1, "11.00", "1.10"] }),
    open_pipeline: open(5, "500018.00", "125002.05"),
    won_in_horizon: { count: 2, total_amount: "150000.00" },
    projected_in_horizon_amount: "275000.25",
    in_horizon_open: open(3, "500000.00", "125000.25", {
      PIPELINE: [1, "50000.00", "5000.00"],
      BEST_CASE: [1, "150000.00", "20000.00"],
      COMMIT: [1, "300000.00", "100000.25"],
    }),
    commit_scenario_amount: "450000.00",
    best_case_scenario_amount: "600000.00",
    stage_probabilities: [],
    assumptions: [],
    excluded_other_currency_count: 0,
    ...overrides,
  };
}

function renderSection(value = forecast()) {
  return render(<ForecastCategories forecast={value} />);
}

function scenario(term: string) {
  const dt = screen.getByText(term, { selector: "dt" });
  return dt.parentElement as HTMLElement;
}

function breakdownTable() {
  return screen.getAllByRole("table").find((table) => !table.closest(".sr-only")) as HTMLElement;
}

describe("ForecastCategories", () => {
  it("renders the section with scenarios, chart and breakdown", () => {
    renderSection();
    expect(screen.getByRole("region", { name: "Forecast categories" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Scenarios for this horizon" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Open pipeline by category" })).toBeInTheDocument();
    expect(
      screen.getByText(/Open deals expected to close Oct 1, 2026 – Mar 31, 2027/),
    ).toHaveTextContent("Past-due and beyond-horizon deals are not included.");
  });

  it("shows scenario totals exactly as returned, each labelled for what it is", () => {
    renderSection(
      // Deliberately not won + categories: the UI must never recompute scenarios.
      forecast({ commit_scenario_amount: "111.11", best_case_scenario_amount: "222.22" }),
    );
    expect(scenario("Won revenue (actual)")).toHaveTextContent("₹1,50,000.00");
    expect(scenario("Won revenue (actual)")).toHaveAttribute("data-kind", "actual");
    expect(scenario("Commit scenario")).toHaveTextContent("₹111.11");
    expect(scenario("Commit scenario")).toHaveTextContent("Won plus the full value of 1 deal in Commit.");
    expect(scenario("Best case scenario")).toHaveTextContent("₹222.22");
    expect(scenario("Best case scenario")).toHaveTextContent(
      "Commit scenario plus the full value of 1 deal in Best case.",
    );
    expect(scenario("Commit scenario")).toHaveAttribute("data-kind", "scenario");
    expect(scenario("Projected revenue (estimate)")).toHaveTextContent("₹2,75,000.25");
    expect(scenario("Projected revenue (estimate)")).toHaveAttribute("data-kind", "estimate");
    expect(screen.queryByText("₹4,50,000.00")).not.toBeInTheDocument();
  });

  it("explains that scenarios use full unweighted amounts and are not guaranteed", () => {
    renderSection();
    const explanation = screen.getByText(/Commit and Best case add the full, unweighted value/);
    expect(explanation).toHaveTextContent("not guaranteed revenue");
    expect(explanation).toHaveTextContent("Best case already includes Commit; Pipeline deals are in neither.");
  });

  it("opens a category's deals from its row without changing the figures", async () => {
    const onOpenCategory = vi.fn();
    render(<ForecastCategories forecast={forecast()} onOpenCategory={onOpenCategory} />);
    const table = breakdownTable();
    await userEvent.click(within(table).getByRole("button", { name: "View 1 deal in Best case" }));
    expect(onOpenCategory).toHaveBeenCalledWith("BEST_CASE");
    // Three category rows open deals; the total row does not.
    expect(within(table).getAllByRole("button")).toHaveLength(3);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(within(rows[0]!).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "CommitSeller expects to close",
      "1",
      "₹3,00,000.00",
      "₹1,00,000.25",
    ]);
  });

  it("keeps category rows static when nothing handles them", () => {
    renderSection();
    expect(within(breakdownTable()).queryByRole("button")).not.toBeInTheDocument();
  });

  it("lists every category with deal counts, full and weighted amounts", () => {
    renderSection();
    const table = breakdownTable();
    expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual([
      "Category",
      "Deals",
      "Full amount",
      "Weighted (est.)",
    ]);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((row) => within(row).getAllByRole("cell").map((cell) => cell.textContent))).toEqual([
      ["CommitSeller expects to close", "1", "₹3,00,000.00", "₹1,00,000.25"],
      ["Best caseCould close with upside", "1", "₹1,50,000.00", "₹20,000.00"],
      ["PipelineNot yet committed", "1", "₹50,000.00", "₹5,000.00"],
      ["All open in horizonEvery category", "3", "₹5,00,000.00", "₹1,25,000.25"],
    ]);
  });

  it("draws one stacked bar per period with full category amounts", () => {
    renderSection();
    const chart = screen.getByRole("group", { name: "Open pipeline by forecast category and quarter" });
    const bars = within(chart).getAllByRole("button");
    expect(bars).toHaveLength(2);
    const compact = (amount: string) => formatMoneyCompact(amount, "INR");
    expect(bars[0]).toHaveAccessibleName(
      `Q4 2026: total ${compact("500000.00")}; Commit ${compact("300000.00")}, Best case ${compact("150000.00")}, Pipeline ${compact("50000.00")}`,
    );
    expect(
      Array.from(bars[0]!.querySelectorAll("[data-series]")).map((segment) => segment.getAttribute("data-series")),
    ).toEqual(["COMMIT", "BEST_CASE", "PIPELINE"]);
    // A period with no open deals draws no segments at all.
    expect(bars[1]!.querySelectorAll("[data-series]")).toHaveLength(0);
    const legend = screen.getByRole("list", { name: "Legend: Open pipeline by forecast category and quarter" });
    expect(within(legend).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Commit",
      "Best case",
      "Pipeline",
    ]);
  });

  it("offers the chart's figures as a table for assistive technology", () => {
    renderSection();
    const table = screen.getAllByRole("table").find((element) => element.closest(".sr-only"))!;
    expect(within(table).getByText("Open pipeline by forecast category and quarter")).toBeInTheDocument();
    const q4 = within(table).getByRole("row", { name: /Q4 2026/ });
    expect(within(q4).getAllByRole("cell")).toHaveLength(4);
    expect(within(table).getByRole("row", { name: /Q1 2027/ })).toBeInTheDocument();
  });

  it("shows a tooltip on keyboard focus", async () => {
    const user = userEvent.setup();
    renderSection();
    await user.tab();
    const tooltip = await screen.findByRole("tooltip");
    expect(tooltip).toHaveTextContent("Q4 2026");
    expect(tooltip).toHaveTextContent(`Commit: ${formatMoneyCompact("300000.00", "INR")}`);
  });

  it("handles a horizon with no open deals and zero scenarios", () => {
    renderSection(
      forecast({
        periods: [period("2026-11", "2026-11-01", "2026-11-30", zero)],
        granularity: "month",
        in_horizon_open: zero,
        won_in_horizon: { count: 0, total_amount: "0.00" },
        commit_scenario_amount: "0.00",
        best_case_scenario_amount: "0.00",
        projected_in_horizon_amount: "0.00",
      }),
    );
    expect(screen.getByText("No open deals are expected to close in this horizon.")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /by forecast category/ })).not.toBeInTheDocument();
    expect(scenario("Commit scenario")).toHaveTextContent("₹0.00");
    expect(scenario("Commit scenario")).toHaveTextContent("0 deals in Commit");
    expect(scenario("Best case scenario")).toHaveTextContent("₹0.00");
    const rows = within(breakdownTable()).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(4);
    for (const row of rows) {
      const [, count, full, weighted] = within(row).getAllByRole("cell");
      expect(count).toHaveTextContent("0");
      expect(full).toHaveTextContent("₹0.00");
      expect(weighted).toHaveTextContent("₹0.00");
      // Zero values recede rather than disappear.
      expect(full!.firstElementChild).toHaveClass("text-muted-foreground");
    }
  });

  it("treats a category missing from the response as zero", () => {
    const inHorizon = forecast().in_horizon_open!;
    renderSection(
      forecast({
        in_horizon_open: {
          ...inHorizon,
          category_totals: inHorizon.category_totals!.filter((row) => row.category !== "BEST_CASE"),
        },
      }),
    );
    const row = within(breakdownTable()).getByRole("row", { name: /Best case/ });
    expect(within(row).getAllByRole("cell").map((cell) => cell.textContent).slice(1)).toEqual([
      "0",
      "₹0.00",
      "₹0.00",
    ]);
  });

  it("explains missing category data from an older API instead of crashing", () => {
    // A backend running pre-4C-2 code returns none of the category fields.
    const older = forecast();
    delete older.in_horizon_open;
    delete older.commit_scenario_amount;
    delete older.best_case_scenario_amount;
    for (const item of [...older.periods.map((p) => p.open), older.past_due, older.beyond_horizon, older.open_pipeline]) {
      delete item.category_totals;
    }
    renderSection(older);
    expect(screen.getByRole("region", { name: "Forecast categories" })).toBeInTheDocument();
    expect(screen.getByText("Category totals unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Commit scenario")).not.toBeInTheDocument();
    expect(screen.queryByText("₹0.00")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("uses month labels for a monthly forecast", () => {
    renderSection(
      forecast({
        granularity: "month",
        periods: [period("2026-11", "2026-11-01", "2026-11-30", open(1, "10.00", "1.00", { COMMIT: [1, "10.00", "1.00"] }))],
      }),
    );
    const chart = screen.getByRole("group", { name: "Open pipeline by forecast category and month" });
    expect(within(chart).getByRole("button")).toHaveAccessibleName(/^November 2026: total/);
    expect(screen.getByText("Full, unweighted value of open deals expected to close in each month.")).toBeInTheDocument();
  });

  it("stacks on small screens and sits side by side on wide ones", () => {
    renderSection();
    const chartCard = screen.getByRole("region", { name: "Open pipeline by category" });
    expect(chartCard.parentElement).toHaveClass("grid", "xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]");
    const scenarios = screen.getByRole("region", { name: "Scenarios for this horizon" }).querySelector("dl");
    expect(scenarios).toHaveClass("grid", "sm:grid-cols-2", "xl:grid-cols-4");
  });
});
