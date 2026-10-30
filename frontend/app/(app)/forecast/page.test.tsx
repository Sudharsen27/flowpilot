import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ForecastPage from "@/app/(app)/forecast/page";
import { QueryProvider } from "@/components/providers/query-provider";
import { ApiError } from "@/lib/api/client";
import { getPipelineForecast } from "@/lib/api/pipeline";
import { notifySalesTargetsChanged } from "@/lib/deal-events";
import { createQueryClient } from "@/lib/query-client";
import type {
  ForecastCategory,
  ForecastCategoryTotals,
  ForecastGranularity,
  ForecastPeriod,
  ForecastTarget,
  PipelineForecast,
} from "@/types/api";

const mockReplace = vi.fn();
let currentSearch = "";
const listeners = new Set<() => void>();

vi.mock("next/navigation", async () => {
  const React = await import("react");
  return {
    useRouter: () => ({
      replace: (href: string, options?: { scroll?: boolean }) => {
        mockReplace(href, options);
        currentSearch = href.includes("?") ? (href.split("?")[1] ?? "") : "";
        for (const listener of listeners) listener();
      },
      push: vi.fn(),
    }),
    usePathname: () => "/forecast",
    useSearchParams: () => {
      React.useSyncExternalStore(
        (notify) => {
          listeners.add(notify);
          return () => listeners.delete(notify);
        },
        () => currentSearch,
        () => currentSearch,
      );
      return new URLSearchParams(currentSearch);
    },
  };
});

vi.mock("@/lib/api/pipeline", () => ({ getPipelineForecast: vi.fn() }));

const authMock = vi.hoisted(() => ({ role: "OWNER" as string }));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    session: {
      user: { id: "user-1", name: "Olivia Owner", email: "o@example.com" },
      organization: { id: "org-1", name: "Acme", slug: "acme" },
      membership: { role: authMock.role },
    },
    isLoading: false,
  }),
}));

const forecastMock = vi.mocked(getPipelineForecast);

/** A fresh cache per test; no retry back-off so retry behaviour runs instantly. */
function renderPage(client = createQueryClient({ retryDelay: 0 })) {
  return render(
    <QueryProvider client={client}>
      <ForecastPage />
    </QueryProvider>,
  );
}

/** The forecast request for a horizon, sent with an abort signal. */
function requested(granularity: ForecastGranularity, periods: number) {
  return [{ granularity, periods }, { signal: expect.any(AbortSignal) }] as const;
}

/** Category totals in the API's order; unlisted categories are zero. */
function categories(
  values: Partial<Record<ForecastCategory, [count: number, total: string, weighted: string]>> = {},
): ForecastCategoryTotals[] {
  return (["PIPELINE", "BEST_CASE", "COMMIT"] as const).map((category) => {
    const [count, total_amount, weighted_amount] = values[category] ?? [0, "0.00", "0.00"];
    return { category, count, total_amount, weighted_amount };
  });
}

const zeroOpen = {
  count: 0,
  total_amount: "0.00",
  weighted_amount: "0.00",
  override_count: 0,
  category_totals: categories(),
};

/** The period table; the category section has its own tables. */
function periodTable() {
  return within(screen.getByRole("region", { name: /^Forecast by (quarter|month)$/ })).getByRole("table");
}

async function findPeriodTable() {
  const section = await screen.findByRole("region", { name: /^Forecast by (quarter|month)$/ });
  return within(section).getByRole("table");
}

function period(overrides: Partial<ForecastPeriod> & Pick<ForecastPeriod, "label" | "period_start" | "period_end">): ForecastPeriod {
  return {
    won: { count: 0, total_amount: "0.00" },
    open: zeroOpen,
    projected_amount: "0.00",
    ...overrides,
  };
}

const quarterPeriods: ForecastPeriod[] = [
  period({
    label: "2026-Q4",
    period_start: "2026-10-01",
    period_end: "2026-12-31",
    won: { count: 2, total_amount: "150000.00" },
    open: {
      count: 3,
      total_amount: "500000.00",
      weighted_amount: "125000.25",
      override_count: 1,
      category_totals: categories({
        PIPELINE: [1, "50000.00", "5000.00"],
        BEST_CASE: [1, "150000.00", "20000.00"],
        COMMIT: [1, "300000.00", "100000.25"],
      }),
    },
    projected_amount: "275000.25",
  }),
  period({
    label: "2027-Q1",
    period_start: "2027-01-01",
    period_end: "2027-03-31",
    open: {
      count: 1,
      total_amount: "80000.00",
      weighted_amount: "40000.00",
      override_count: 0,
      category_totals: categories({ BEST_CASE: [1, "80000.00", "40000.00"] }),
    },
    projected_amount: "40000.00",
  }),
  period({ label: "2027-Q2", period_start: "2027-04-01", period_end: "2027-06-30" }),
  period({
    label: "2027-Q3",
    period_start: "2027-07-01",
    period_end: "2027-09-30",
    open: {
      count: 1,
      total_amount: "20000.00",
      weighted_amount: "5000.00",
      override_count: 0,
      category_totals: categories({ PIPELINE: [1, "20000.00", "5000.00"] }),
    },
    projected_amount: "5000.00",
  }),
];

function monthPeriods(count: number): ForecastPeriod[] {
  return Array.from({ length: count }, (_, index) => {
    const month = ((9 + index) % 12) + 1;
    const year = 2026 + Math.floor((9 + index) / 12);
    const mm = String(month).padStart(2, "0");
    return period({
      label: `${year}-${mm}`,
      period_start: `${year}-${mm}-01`,
      period_end: `${year}-${mm}-28`,
      won: index === 0 ? { count: 1, total_amount: "1000.00" } : { count: 0, total_amount: "0.00" },
      projected_amount: index === 0 ? "1000.00" : "0.00",
    });
  });
}

function forecast(overrides: Partial<PipelineForecast> = {}): PipelineForecast {
  return {
    currency: "INR",
    as_of: "2026-10-29T06:30:00Z",
    granularity: "quarter",
    method: "STAGE_PROBABILITY_WEIGHTED",
    rounding: "PER_DEAL_HALF_UP_CENTS",
    horizon_start: "2026-10-01",
    horizon_end: "2027-09-30",
    periods: quarterPeriods,
    past_due: {
      count: 2,
      total_amount: "60000.00",
      weighted_amount: "15000.00",
      override_count: 0,
      category_totals: categories({ PIPELINE: [1, "20000.00", "5000.00"], COMMIT: [1, "40000.00", "10000.00"] }),
      oldest_expected_close_date: "2026-08-15",
    },
    beyond_horizon: {
      count: 1,
      total_amount: "90000.00",
      weighted_amount: "45000.00",
      override_count: 0,
      category_totals: categories({ BEST_CASE: [1, "90000.00", "45000.00"] }),
    },
    open_pipeline: {
      count: 8,
      total_amount: "750000.00",
      weighted_amount: "230000.25",
      override_count: 1,
      category_totals: categories({
        PIPELINE: [3, "90000.00", "15000.00"],
        BEST_CASE: [3, "320000.00", "105000.00"],
        COMMIT: [2, "340000.00", "110000.25"],
      }),
    },
    won_in_horizon: { count: 2, total_amount: "150000.00" },
    projected_in_horizon_amount: "320000.25",
    in_horizon_open: {
      count: 5,
      total_amount: "600000.00",
      weighted_amount: "170000.25",
      override_count: 1,
      category_totals: categories({
        PIPELINE: [2, "70000.00", "10000.00"],
        BEST_CASE: [2, "230000.00", "60000.00"],
        COMMIT: [1, "300000.00", "100000.25"],
      }),
    },
    commit_scenario_amount: "450000.00",
    best_case_scenario_amount: "680000.00",
    stage_probabilities: [
      { stage: "QUALIFICATION", default_probability: 10 },
      { stage: "DISCOVERY", default_probability: 25 },
      { stage: "PROPOSAL", default_probability: 50 },
      { stage: "NEGOTIATION", default_probability: 75 },
      { stage: "CLOSED_WON", default_probability: 100 },
      { stage: "CLOSED_LOST", default_probability: 0 },
    ],
    assumptions: [
      {
        code: "STAGE_PROBABILITY_WEIGHTING",
        detail: "Each open deal is weighted by its stage's default probability unless the deal has a manual override.",
      },
      {
        code: "NO_HISTORICAL_WIN_RATES",
        detail: "Probabilities are not calibrated against past outcomes; historical win rates are not used.",
      },
      {
        code: "PAST_DUE_SEPARATED",
        detail: "2 open deal(s) have a past expected close date; they are reported as past due and not forecast into any period.",
      },
    ],
    excluded_other_currency_count: 0,
    ...overrides,
  };
}

function respondByParams() {
  forecastMock.mockImplementation(async ({ granularity, periods }: { granularity: ForecastGranularity; periods: number }) =>
    granularity === "month"
      ? forecast({
          granularity: "month",
          periods: monthPeriods(periods),
          horizon_end: "2027-09-30",
          won_in_horizon: { count: 1, total_amount: "1000.00" },
          in_horizon_open: zeroOpen,
          commit_scenario_amount: "1000.00",
          best_case_scenario_amount: "1000.00",
        })
      : forecast({ periods: quarterPeriods.slice(0, periods) }),
  );
}

describe("Forecast page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "";
    authMock.role = "OWNER";
    respondByParams();
  });

  it("defaults to 4 quarters and requests the forecast once", async () => {
    renderPage();
    await findPeriodTable();
    expect(forecastMock).toHaveBeenCalledTimes(1);
    expect(forecastMock).toHaveBeenCalledWith(...requested("quarter", 4));
    expect(screen.getByRole("button", { name: "Quarter" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Month" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByLabelText("Horizon")).toHaveValue("4");
  });

  it("shows the API's KPI figures exactly", async () => {
    renderPage();
    expect(await screen.findByLabelText("₹1,50,000.00")).toBeInTheDocument();
    expect(screen.getByLabelText("₹2,30,000.25")).toBeInTheDocument();
    expect(screen.getByLabelText("₹3,20,000.25")).toBeInTheDocument();
    expect(screen.getByLabelText("₹7,50,000.00")).toBeInTheDocument();
    // In-horizon figures first, then all-horizon pipeline figures.
    expect(screen.getAllByRole("heading", { level: 3 }).slice(0, 4).map((h) => h.textContent)).toEqual([
      "Won revenue (actual)",
      "Projected revenue (in horizon)",
      "Open pipeline value",
      "Weighted open pipeline (all horizons)",
    ]);
    expect(screen.getByText("2 deals closed won in this horizon.")).toBeInTheDocument();
    expect(
      screen.getByText("Estimate: won plus weighted deals due Oct 1, 2026 – Sep 30, 2027."),
    ).toBeInTheDocument();
    expect(screen.getByText("8 deals open, unweighted.")).toBeInTheDocument();
  });

  it("labels the weighted KPI as all open pipeline, sourced from open_pipeline", async () => {
    // Distinct values: in-horizon period weights, past due, beyond horizon and the
    // all-horizons total differ, so the card can only match open_pipeline.weighted_amount.
    forecastMock.mockResolvedValue(
      forecast({ open_pipeline: { ...forecast().open_pipeline, weighted_amount: "987654.32" } }),
    );
    renderPage();
    const heading = await screen.findByRole("heading", { level: 3, name: "Weighted open pipeline (all horizons)" });
    const card = heading.closest("article") as HTMLElement;
    expect(await within(card).findByLabelText("₹9,87,654.32")).toBeInTheDocument();
    expect(
      within(card).getByText(
        "Estimate across 8 deals open: past-due, in-horizon and beyond-horizon.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Weighted forecast" })).not.toBeInTheDocument();

    // Projected revenue stays a separate KPI from projected_in_horizon_amount.
    const projected = screen
      .getByRole("heading", { level: 3, name: "Projected revenue (in horizon)" })
      .closest("article") as HTMLElement;
    expect(within(projected).getByLabelText("₹3,20,000.25")).toBeInTheDocument();
  });

  it("lists every period with backend values", async () => {
    renderPage();
    const table = await findPeriodTable();
    const headers = within(table).getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual([
      "Period",
      "Won (actual)",
      "Open pipeline",
      "Weighted forecast (est.)",
      "Projected (est.)",
    ]);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(4);
    const q4 = within(table).getByRole("row", { name: /Q4 2026/ });
    expect(within(q4).getByText("₹1,50,000.00")).toBeInTheDocument();
    expect(within(q4).getByText("₹5,00,000.00")).toBeInTheDocument();
    expect(within(q4).getByText("₹1,25,000.25")).toBeInTheDocument();
    expect(within(q4).getByText("₹2,75,000.25")).toBeInTheDocument();
    expect(within(q4).getByText("3 deals")).toBeInTheDocument();
  });

  it("charts actual and weighted values as distinct, labelled series", async () => {
    renderPage();
    const chart = await screen.findByRole("group", { name: "Won revenue and weighted forecast by quarter" });
    const bars = within(chart).getAllByRole("button");
    expect(bars).toHaveLength(4);
    expect(bars[0]).toHaveAccessibleName(
      /^Q4 2026: Won revenue \(actual\) .+, Weighted forecast \(estimate\) .+$/,
    );
    // Q2 2027 has no won or weighted value: its marks are not drawn at all.
    expect(bars[2]?.querySelectorAll("span.invisible")).toHaveLength(2);
    expect(bars[0]?.querySelectorAll("span.invisible")).toHaveLength(0);
    const legend = screen.getByRole("list", { name: "Legend" });
    expect(within(legend).getByText("Weighted forecast (estimate)")).toBeInTheDocument();
    expect(screen.getAllByText(/not committed revenue/).length).toBeGreaterThan(0);
  });

  it("never recomputes figures in the browser", async () => {
    // Deliberately inconsistent totals: the page must show them as returned.
    forecastMock.mockResolvedValue(
      forecast({
        periods: [{ ...quarterPeriods[0]!, projected_amount: "777.77" }],
        projected_in_horizon_amount: "12.34",
        open_pipeline: { ...zeroOpen, count: 8, total_amount: "1.00", weighted_amount: "2.00" },
      }),
    );
    renderPage();
    const table = await findPeriodTable();
    expect(within(table).getByText("₹777.77")).toBeInTheDocument();
    expect(screen.getByLabelText("₹12.34")).toBeInTheDocument();
    expect(screen.getByLabelText("₹1.00")).toBeInTheDocument();
    expect(screen.getByLabelText("₹2.00")).toBeInTheDocument();
    expect(screen.queryByText("₹2,75,000.25")).not.toBeInTheDocument();
  });

  it("switches to 12 months and back to the cached 4 quarters through the URL", async () => {
    const user = userEvent.setup();
    renderPage();
    await findPeriodTable();

    await user.click(screen.getByRole("button", { name: "Month" }));
    expect(mockReplace).toHaveBeenLastCalledWith("/forecast?granularity=month", { scroll: false });
    await waitFor(() => expect(forecastMock).toHaveBeenLastCalledWith(...requested("month", 12)));
    const table = await findPeriodTable();
    await waitFor(() => expect(within(table).getAllByRole("row").slice(1)).toHaveLength(12));
    expect(within(table).getByRole("row", { name: /October 2026/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Forecast by month" })).toBeInTheDocument();
    expect(screen.getByLabelText("Horizon")).toHaveValue("12");

    await user.click(screen.getByRole("button", { name: "Quarter" }));
    expect(mockReplace).toHaveBeenLastCalledWith("/forecast", { scroll: false });
    await waitFor(() =>
      expect(within(periodTable()).getAllByRole("row").slice(1)).toHaveLength(4),
    );
    // The quarter result is still fresh, so returning to it sends no new request.
    expect(forecastMock).toHaveBeenCalledTimes(2);
  });

  it("changes the horizon within backend limits", async () => {
    const user = userEvent.setup();
    renderPage();
    await findPeriodTable();
    const horizon = screen.getByLabelText("Horizon");
    expect(within(horizon).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "2 quarters",
      "4 quarters",
      "6 quarters",
      "8 quarters",
    ]);
    await user.selectOptions(horizon, "2");
    expect(mockReplace).toHaveBeenLastCalledWith("/forecast?periods=2", { scroll: false });
    await waitFor(() => expect(forecastMock).toHaveBeenLastCalledWith(...requested("quarter", 2)));
  });

  it("restores the selection from the URL", async () => {
    currentSearch = "granularity=month&periods=6";
    renderPage();
    await findPeriodTable();
    expect(forecastMock).toHaveBeenCalledWith(...requested("month", 6));
    expect(screen.getByRole("button", { name: "Month" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Horizon")).toHaveValue("6");
  });

  it("ignores an out-of-range URL horizon", async () => {
    currentSearch = "periods=40";
    renderPage();
    await findPeriodTable();
    expect(forecastMock).toHaveBeenCalledWith(...requested("quarter", 4));
  });

  it("shows past-due and beyond-horizon pipeline separately", async () => {
    renderPage();
    const pastDue = await screen.findByRole("region", { name: "Past due" });
    expect(within(pastDue).getByText("₹60,000.00")).toBeInTheDocument();
    expect(within(pastDue).getByText("₹15,000.00")).toBeInTheDocument();
    expect(within(pastDue).getByText("Aug 15, 2026")).toBeInTheDocument();
    expect(within(pastDue).getByText(/2 deals still open after the expected close date/)).toBeInTheDocument();

    const beyond = screen.getByRole("region", { name: "Beyond the horizon" });
    expect(within(beyond).getByText("₹90,000.00")).toBeInTheDocument();
    expect(within(beyond).getByText("₹45,000.00")).toBeInTheDocument();
    expect(within(beyond).getByText("Open deals expected to close after Sep 30, 2027.")).toBeInTheDocument();
  });

  it("shows currency, methodology and backend assumptions", async () => {
    renderPage();
    const section = await screen.findByRole("region", { name: "Methodology and assumptions" });
    const term = (name: string) => within(section).getByText(name, { selector: "dt" }).nextElementSibling;
    expect(term("Currency")).toHaveTextContent("INR");
    expect(term("As of")).toHaveTextContent("2026-10-29 06:30:00 UTC");
    expect(term("Method")).toHaveTextContent("Stage-probability weighted");
    expect(term("Rounding")).toHaveTextContent(/rounded half-up to the cent/);
    expect(term("Horizon")).toHaveTextContent("Oct 1, 2026 – Sep 30, 2027 (4 quarters)");
    expect(term("Stage probabilities")).toHaveTextContent("Proposal 50%");
    expect(
      within(section).getByText(/historical win rates are not used/),
    ).toBeInTheDocument();
    expect(within(section).getByText(/2 open deal\(s\) have a past expected close date/)).toBeInTheDocument();
    expect(within(section).getAllByRole("listitem").filter((item) => item.dataset.code)).toHaveLength(3);
    expect(screen.queryByText("Some deals are not included")).not.toBeInTheDocument();
  });

  it("keeps assumptions in a collapsed disclosure that opens on demand", async () => {
    const user = userEvent.setup();
    renderPage();
    const section = await screen.findByRole("region", { name: "Methodology and assumptions" });
    const summary = within(section).getByText("Assumptions (3)");
    const details = summary.closest("details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    await user.click(summary);
    expect(details.open).toBe(true);
  });

  it("shows when the figures were calculated", async () => {
    renderPage();
    expect(await screen.findByText("As of 2026-10-29 06:30:00 UTC")).toBeInTheDocument();
  });

  it("keeps figures on screen while refreshing, and flags a failed refresh", async () => {
    const user = userEvent.setup();
    const client = createQueryClient({ retryDelay: 0 });
    renderPage(client);
    await screen.findByLabelText("₹1,50,000.00");

    let finish: (value: PipelineForecast) => void = () => {};
    forecastMock.mockImplementationOnce(() => new Promise((resolve) => (finish = resolve)));
    void client.refetchQueries();
    expect(await screen.findByText(/Refreshing…/)).toBeInTheDocument();
    expect(screen.getByLabelText("₹1,50,000.00")).toBeInTheDocument();
    finish(forecast());
    await waitFor(() => expect(screen.queryByText(/Refreshing…/)).not.toBeInTheDocument());

    forecastMock.mockRejectedValue(new ApiError("Request failed: 503", 503));
    void client.refetchQueries();
    expect(
      await screen.findByText(/Could not refresh. Showing figures as of 2026-10-29 06:30:00 UTC./),
    ).toBeInTheDocument();
    // The last good figures stay; this is not the full-page error.
    expect(screen.getByLabelText("₹1,50,000.00")).toBeInTheDocument();
    expect(screen.queryByText("Forecast unavailable")).not.toBeInTheDocument();

    respondByParams();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("As of 2026-10-29 06:30:00 UTC")).toBeInTheDocument();
  });

  it("warns when deals in other currencies are excluded", async () => {
    forecastMock.mockResolvedValue(
      forecast({
        excluded_other_currency_count: 3,
        assumptions: [
          { code: "OTHER_CURRENCY_EXCLUDED", detail: "3 deal(s) in another currency are excluded, not converted." },
        ],
      }),
    );
    renderPage();
    expect(await screen.findByText("Some deals are not included")).toBeInTheDocument();
    expect(
      screen.getByText("3 deals use a currency other than INR. They are excluded from every figure on this page, not converted."),
    ).toBeInTheDocument();
    expect(screen.getByText("3 deal(s) in another currency are excluded, not converted.")).toBeInTheDocument();
  });

  it("shows a loading state while the forecast loads", () => {
    forecastMock.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getAllByText("Loading forecast").length).toBeGreaterThan(0);
    expect(screen.getByText("Loading Won revenue (actual)")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("retries server errors, then shows an error with a working Retry", async () => {
    const user = userEvent.setup();
    forecastMock.mockRejectedValue(new ApiError("Request failed: 500", 500));
    renderPage();
    expect(await screen.findByText("Forecast unavailable")).toBeInTheDocument();
    expect(screen.getByText("The forecast could not be loaded. Your deals are unaffected.")).toBeInTheDocument();
    expect(screen.queryByLabelText("₹1,50,000.00")).not.toBeInTheDocument();
    // One attempt plus two automatic retries.
    expect(forecastMock).toHaveBeenCalledTimes(3);

    respondByParams();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await findPeriodTable()).toBeInTheDocument();
    expect(forecastMock).toHaveBeenCalledTimes(4);
  });

  it("does not retry an unsupported horizon", async () => {
    forecastMock.mockRejectedValue(new ApiError("Request failed: 422", 422));
    renderPage();
    expect(
      await screen.findByText("This forecast horizon is not supported. Choose a shorter horizon."),
    ).toBeInTheDocument();
    expect(forecastMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry an authorization failure", async () => {
    forecastMock.mockRejectedValue(new ApiError("Request failed: 403", 403));
    renderPage();
    expect(
      await screen.findByText("You do not have access to this organization's forecast."),
    ).toBeInTheDocument();
    expect(forecastMock).toHaveBeenCalledTimes(1);
  });

  it("aborts a superseded request and never shows the previous horizon's figures", async () => {
    const user = userEvent.setup();
    const signals: AbortSignal[] = [];
    forecastMock.mockImplementation((params, options) => {
      if (options?.signal) signals.push(options.signal);
      return params.granularity === "quarter"
        ? Promise.resolve(forecast())
        : new Promise(() => {});
    });
    renderPage();
    await findPeriodTable();

    await user.click(screen.getByRole("button", { name: "Month" }));
    await waitFor(() => expect(forecastMock).toHaveBeenLastCalledWith(...requested("month", 12)));
    // Month is still loading: the quarter figures must not stand in for it.
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("₹1,50,000.00")).not.toBeInTheDocument();
    expect(screen.getAllByText("Loading forecast").length).toBeGreaterThan(0);

    // Going back cancels the pending month request and reuses the cached quarter.
    await user.click(screen.getByRole("button", { name: "Quarter" }));
    expect(await findPeriodTable()).toBeInTheDocument();
    expect(signals[1]?.aborted).toBe(true);
    expect(forecastMock).toHaveBeenCalledTimes(2);
  });

  it("shows an empty state when there is nothing to forecast", async () => {
    forecastMock.mockResolvedValue(
      forecast({
        periods: quarterPeriods.map((item) => ({ ...item, won: { count: 0, total_amount: "0.00" }, open: zeroOpen, projected_amount: "0.00" })),
        past_due: { ...zeroOpen, oldest_expected_close_date: null },
        beyond_horizon: zeroOpen,
        open_pipeline: zeroOpen,
        won_in_horizon: { count: 0, total_amount: "0.00" },
        projected_in_horizon_amount: "0.00",
        in_horizon_open: zeroOpen,
        commit_scenario_amount: "0.00",
        best_case_scenario_amount: "0.00",
      }),
    );
    renderPage();
    expect(await screen.findByText("No deals to forecast yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New deal" })).toHaveAttribute("href", "/deals?create=1");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /by quarter/ })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Methodology and assumptions" })).toBeInTheDocument();
  });
  describe("forecast categories", () => {
    function categoriesRegion() {
      return screen.findByRole("region", { name: "Forecast categories" });
    }

    it("shows the category section between the periods and the outside-horizon pipeline", async () => {
      renderPage();
      const region = await categoriesRegion();
      const headings = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
      const at = (title: string) => headings.indexOf(title);
      expect(at("Forecast by quarter")).toBeLessThan(at("Forecast categories"));
      expect(at("Forecast categories")).toBeLessThan(at("Pipeline outside the forecast periods"));
      expect(within(region).getByText("Commit scenario", { selector: "dt" }).parentElement).toHaveTextContent(
        "₹4,50,000.00",
      );
      expect(within(region).getByText("Best case scenario", { selector: "dt" }).parentElement).toHaveTextContent(
        "₹6,80,000.00",
      );
      const breakdown = within(region)
        .getAllByRole("table")
        .find((table) => !table.closest(".sr-only")) as HTMLElement;
      const commit = within(breakdown).getByRole("row", { name: /^Commit/ });
      expect(within(commit).getAllByRole("cell").map((cell) => cell.textContent).slice(1)).toEqual([
        "1",
        "₹3,00,000.00",
        "₹1,00,000.25",
      ]);
      const bestCase = within(breakdown).getByRole("row", { name: /^Best case/ });
      expect(within(bestCase).getByText("₹2,30,000.00")).toBeInTheDocument();
      expect(within(region).getByText(/full, unweighted value/)).toHaveTextContent("not guaranteed revenue");
      // Existing figures stay where they were.
      expect(screen.getByRole("region", { name: "Past due" })).toBeInTheDocument();
      expect(screen.getByRole("region", { name: "Methodology and assumptions" })).toBeInTheDocument();
    });

    it("follows month and quarter switching", async () => {
      const user = userEvent.setup();
      renderPage();
      await categoriesRegion();
      expect(screen.getByRole("group", { name: "Open pipeline by forecast category and quarter" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "Month" }));
      expect(await screen.findByText("No open deals are expected to close in this horizon.")).toBeInTheDocument();
      const region = await categoriesRegion();
      expect(within(region).getByText("Commit scenario", { selector: "dt" }).parentElement).toHaveTextContent(
        "₹1,000.00",
      );
      expect(currentSearch).toBe("granularity=month");

      await user.click(screen.getByRole("button", { name: "Quarter" }));
      expect(
        await screen.findByRole("group", { name: "Open pipeline by forecast category and quarter" }),
      ).toBeInTheDocument();
      expect(forecastMock).toHaveBeenCalledTimes(2);
    });

    it("keeps the rest of the page working when the API has no category totals", async () => {
      const older = forecast();
      delete older.in_horizon_open;
      delete older.commit_scenario_amount;
      delete older.best_case_scenario_amount;
      forecastMock.mockResolvedValue(older);
      renderPage();
      expect(await screen.findByText("Category totals unavailable")).toBeInTheDocument();
      expect(await findPeriodTable()).toBeInTheDocument();
      expect(screen.getByLabelText("₹3,20,000.25")).toBeInTheDocument();
      expect(screen.getByRole("region", { name: "Past due" })).toBeInTheDocument();
    });

    it("is not shown while loading, on error or when there is nothing to forecast", async () => {
      forecastMock.mockReturnValue(new Promise(() => {}));
      const { unmount } = renderPage();
      expect(screen.queryByRole("region", { name: "Forecast categories" })).not.toBeInTheDocument();
      unmount();

      forecastMock.mockRejectedValue(new ApiError("Request failed: 403", 403));
      const failed = renderPage();
      expect(await screen.findByText("Forecast unavailable")).toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "Forecast categories" })).not.toBeInTheDocument();
      failed.unmount();

      forecastMock.mockResolvedValue(
        forecast({
          periods: quarterPeriods.map((item) => ({ ...item, won: { count: 0, total_amount: "0.00" }, open: zeroOpen, projected_amount: "0.00" })),
          past_due: { ...zeroOpen, oldest_expected_close_date: null },
          beyond_horizon: zeroOpen,
          open_pipeline: zeroOpen,
          in_horizon_open: zeroOpen,
          won_in_horizon: { count: 0, total_amount: "0.00" },
          projected_in_horizon_amount: "0.00",
          commit_scenario_amount: "0.00",
          best_case_scenario_amount: "0.00",
        }),
      );
      renderPage();
      expect(await screen.findByText("No deals to forecast yet")).toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "Forecast categories" })).not.toBeInTheDocument();
    });
  });
  describe("progress to target", () => {
    const noTarget: ForecastTarget = {
      status: "NONE",
      amount: null,
      months_in_range: 3,
      months_with_target: 0,
      missing_months: ["2027-04-01", "2027-05-01", "2027-06-01"],
      has_owner_targets: false,
      comparisons: [],
    };
    const fullTarget: ForecastTarget = {
      status: "FULL",
      amount: "300000.00",
      months_in_range: 3,
      months_with_target: 3,
      missing_months: [],
      has_owner_targets: false,
      comparisons: [
        { basis: "WON", amount: "150000.00", attainment_percent: "50.0", remaining_amount: "150000.00", above_target_amount: "0.00" },
        { basis: "COMMIT_SCENARIO", amount: "450000.00", attainment_percent: "150.0", remaining_amount: "0.00", above_target_amount: "150000.00" },
        { basis: "BEST_CASE_SCENARIO", amount: "600000.00", attainment_percent: "200.0", remaining_amount: "0.00", above_target_amount: "300000.00" },
        { basis: "PROJECTED", amount: "275000.25", attainment_percent: "91.7", remaining_amount: "24999.75", above_target_amount: "0.00" },
      ],
    };

    /** The quarter fixture with target fields, as the Slice 4D API returns it. */
    function withTargets(horizon: ForecastTarget): PipelineForecast {
      return forecast({
        periods: quarterPeriods.map((item, index) => ({
          ...item,
          commit_scenario_amount: index === 0 ? "450000.00" : "0.00",
          best_case_scenario_amount: index === 0 ? "600000.00" : "0.00",
          target: index === 0 ? fullTarget : noTarget,
        })),
        target_in_horizon: horizon,
      });
    }

    function targetsRegion() {
      return screen.findByRole("region", { name: "Progress to target" });
    }

    it("sits directly after the KPI cards, before the chart and period table", async () => {
      forecastMock.mockResolvedValue(withTargets({ ...noTarget, months_in_range: 12, missing_months: ["2027-04-01"] }));
      renderPage();
      const region = await targetsRegion();
      const summary = screen.getByRole("region", { name: "Forecast summary" });
      const periods = screen.getByRole("region", { name: "Forecast by quarter" });
      expect(summary.compareDocumentPosition(region) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(region.compareDocumentPosition(periods) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      const headings = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
      expect(headings.indexOf("Progress to target")).toBe(headings.indexOf("Forecast summary") + 1);
    });

    it("shows the API's target figures and per-period attainment", async () => {
      forecastMock.mockResolvedValue(withTargets(fullTarget));
      renderPage();
      const region = await targetsRegion();
      const card = within(region).getByRole("region", { name: "Target for this horizon" });
      expect(card).toHaveTextContent("₹3,00,000.00");
      expect(card).toHaveTextContent("91.7% of target");
      expect(card).toHaveTextContent("₹24,999.75 to go");
      expect(card).toHaveTextContent("Above target by ₹1,50,000.00");
      const q4 = within(region).getByRole("row", { name: /^Q4 2026/ });
      expect(q4).toHaveTextContent("50.0% of target");
      const q2 = within(region).getByRole("row", { name: /^Q2 2027/ });
      expect(q2).toHaveTextContent("Not set");
      expect(q2).not.toHaveTextContent("% of target");
      // KPI cards are unchanged by the targets section.
      expect(screen.getByLabelText("₹3,20,000.25")).toBeInTheDocument();
    });

    it.each([
      ["OWNER", true],
      ["ADMIN", true],
      ["MEMBER", false],
    ])("offers Set targets to %s: %s", async (role, offered) => {
      authMock.role = role;
      forecastMock.mockResolvedValue(withTargets({ ...noTarget, months_in_range: 12, missing_months: ["2027-04-01"] }));
      renderPage();
      const region = await targetsRegion();
      const link = within(region).queryByRole("link", { name: "Set targets" });
      if (offered) {
        expect(link).toHaveAttribute("href", "/deals/targets?year=2027");
      } else {
        expect(link).not.toBeInTheDocument();
        expect(region).toHaveTextContent("Owners and admins can set organization targets.");
      }
    });

    it("refetches the forecast after a sales target save", async () => {
      forecastMock.mockResolvedValue(withTargets(noTarget));
      renderPage();
      await targetsRegion();
      expect(forecastMock).toHaveBeenCalledTimes(1);
      forecastMock.mockResolvedValue(withTargets(fullTarget));
      act(() => notifySalesTargetsChanged());
      await waitFor(() => expect(forecastMock).toHaveBeenCalledTimes(2));
      const card = within(await targetsRegion()).getByRole("region", { name: "Target for this horizon" });
      await waitFor(() => expect(card).toHaveTextContent("91.7% of target"));
    });

    it("explains an older API without target figures and keeps the rest of the page", async () => {
      renderPage();
      const region = await targetsRegion();
      expect(within(region).getByText("Target comparison unavailable")).toBeInTheDocument();
      expect(screen.getByRole("region", { name: "Forecast categories" })).toBeInTheDocument();
    });

    it("is not shown when there is nothing to forecast", async () => {
      forecastMock.mockResolvedValue(
        forecast({
          periods: quarterPeriods.map((item) => ({ ...item, won: { count: 0, total_amount: "0.00" }, open: zeroOpen })),
          open_pipeline: zeroOpen,
          won_in_horizon: { count: 0, total_amount: "0.00" },
        }),
      );
      renderPage();
      expect(await screen.findByText("No deals to forecast yet")).toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "Progress to target" })).not.toBeInTheDocument();
    });
  });
});
