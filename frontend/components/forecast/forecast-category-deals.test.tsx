import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ForecastPage from "@/app/(app)/forecast/page";
import { QueryProvider } from "@/components/providers/query-provider";
import { ApiError } from "@/lib/api/client";
import { getForecastCategoryDeals, getPipelineForecast } from "@/lib/api/pipeline";
import { correctedOffset } from "@/components/forecast/forecast-category-deals";
import { notifyDealsChanged } from "@/lib/deal-events";
import { createQueryClient } from "@/lib/query-client";
import type {
  ForecastCategory,
  ForecastCategoryDeal,
  ForecastCategoryDeals,
  ForecastCategoryTotals,
  ForecastPeriod,
  PipelineForecast,
} from "@/types/api";

let currentSearch = "";
const listeners = new Set<() => void>();

vi.mock("next/navigation", async () => {
  const React = await import("react");
  return {
    useRouter: () => ({
      replace: (href: string) => {
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

vi.mock("@/lib/api/pipeline", () => ({
  getPipelineForecast: vi.fn(),
  getForecastCategoryDeals: vi.fn(),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    session: {
      user: { id: "user-1", name: "Olivia Owner", email: "o@example.com" },
      organization: { id: "org-1", name: "Acme", slug: "acme" },
      membership: { role: "MEMBER" },
    },
    isLoading: false,
  }),
}));

const forecastMock = vi.mocked(getPipelineForecast);
const dealsMock = vi.mocked(getForecastCategoryDeals);

function categories(
  values: Partial<Record<ForecastCategory, [number, string, string]>> = {},
): ForecastCategoryTotals[] {
  return (["PIPELINE", "BEST_CASE", "COMMIT"] as const).map((category) => {
    const [count, total_amount, weighted_amount] = values[category] ?? [0, "0.00", "0.00"];
    return { category, count, total_amount, weighted_amount };
  });
}

function open(values: Partial<Record<ForecastCategory, [number, string, string]>>) {
  return { count: 0, total_amount: "0.00", weighted_amount: "0.00", override_count: 0, category_totals: categories(values) };
}

const periods: ForecastPeriod[] = [
  ["2026-Q4", "2026-10-01", "2026-12-31"],
  ["2027-Q1", "2027-01-01", "2027-03-31"],
  ["2027-Q2", "2027-04-01", "2027-06-30"],
  ["2027-Q3", "2027-07-01", "2027-09-30"],
].map(([label, period_start, period_end]) => ({
  label: label!,
  period_start: period_start!,
  period_end: period_end!,
  won: { count: 0, total_amount: "0.00" },
  open: open({ COMMIT: [1, "100.00", "75.00"] }),
  projected_amount: "75.00",
}));

function forecast(overrides: Partial<PipelineForecast> = {}): PipelineForecast {
  const inHorizon = open({ PIPELINE: [3, "300.00", "30.00"], BEST_CASE: [0, "0.00", "0.00"], COMMIT: [45, "4500.00", "3375.00"] });
  return {
    currency: "INR",
    as_of: "2026-10-29T06:30:00Z",
    granularity: "quarter",
    method: "STAGE_PROBABILITY_WEIGHTED",
    rounding: "PER_DEAL_HALF_UP_CENTS",
    horizon_start: "2026-10-01",
    horizon_end: "2027-09-30",
    periods,
    past_due: { ...open({}), oldest_expected_close_date: null },
    beyond_horizon: open({}),
    open_pipeline: { ...inHorizon, count: 48, total_amount: "4800.00", weighted_amount: "3405.00" },
    won_in_horizon: { count: 0, total_amount: "0.00" },
    projected_in_horizon_amount: "3405.00",
    in_horizon_open: { ...inHorizon, count: 48, total_amount: "4800.00", weighted_amount: "3405.00" },
    commit_scenario_amount: "4500.00",
    best_case_scenario_amount: "4500.00",
    stage_probabilities: [],
    assumptions: [],
    excluded_other_currency_count: 0,
    ...overrides,
  };
}

function deal(index: number, overrides: Partial<ForecastCategoryDeal> = {}): ForecastCategoryDeal {
  return {
    id: `deal-${index}`,
    name: `Deal ${index}`,
    amount: "100.00",
    currency: "INR",
    stage: "NEGOTIATION",
    probability: null,
    effective_probability: 75,
    probability_source: "STAGE_DEFAULT",
    forecast_category: "COMMIT",
    weighted_amount: "75.00",
    expected_close_date: "2026-11-15",
    period_start: "2026-10-01",
    owner_user_id: "user-1",
    owner_name: "Olivia Owner",
    ...overrides,
  };
}

/** A page of the API response: totals always cover all `total` deals. */
function page(
  offset: number,
  total: number,
  overrides: Partial<ForecastCategoryDeals> = {},
  items?: ForecastCategoryDeal[],
): ForecastCategoryDeals {
  const count = Math.max(0, Math.min(20, total - offset));
  return {
    currency: "INR",
    as_of: "2026-10-29T06:30:00Z",
    granularity: "quarter",
    rounding: "PER_DEAL_HALF_UP_CENTS",
    category: "COMMIT",
    horizon_start: "2026-10-01",
    horizon_end: "2027-09-30",
    range_start: "2026-10-01",
    range_end: "2027-09-30",
    totals: { count: total, total_amount: "4500.00", weighted_amount: "3375.00" },
    items: items ?? Array.from({ length: count }, (_, i) => deal(offset + i + 1)),
    limit: 20,
    offset,
    total,
    ...overrides,
  };
}

function renderPage(client = createQueryClient({ retryDelay: 0 })) {
  render(
    <QueryProvider client={client}>
      <ForecastPage />
    </QueryProvider>,
  );
  return client;
}

/** The desktop table's trigger; DataTable also renders a mobile list that CSS hides. */
async function categoryButton(name: RegExp | string) {
  const [first] = await screen.findAllByRole("button", { name });
  return first!;
}

async function openCategory(name: RegExp) {
  const user = userEvent.setup();
  const trigger = await categoryButton(name);
  await user.click(trigger);
  const dialog = await screen.findByRole("dialog");
  return { user, trigger, dialog };
}

function lastDealsRequest() {
  return dealsMock.mock.calls.at(-1);
}

describe("Forecast category drill-down", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "";
    forecastMock.mockResolvedValue(forecast());
    dealsMock.mockImplementation(async ({ offset }) => page(offset, 45));
  });

  it("makes each category total a labelled button and leaves the total row static", async () => {
    renderPage();
    expect(await categoryButton("View 45 deals in Commit")).toHaveAttribute("aria-haspopup", "dialog");
    expect(await categoryButton("View 0 deals in Best case")).toBeInTheDocument();
    expect(await categoryButton("View 3 deals in Pipeline")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /All open in horizon/ })).not.toBeInTheDocument();
  });

  it("requests the whole horizon of the page's granularity, with an abort signal", async () => {
    renderPage();
    const { dialog } = await openCategory(/in Commit$/);
    expect(within(dialog).getByRole("heading", { name: "Commit deals" })).toBeInTheDocument();
    expect(lastDealsRequest()).toEqual([
      { category: "COMMIT", granularity: "quarter", periods: 4, periodStart: null, limit: 20, offset: 0 },
      { signal: expect.any(AbortSignal) },
    ]);
    expect(within(dialog).getByLabelText("Period")).toHaveValue("");
  });

  it("shows the API's totals across every page, not a sum of the visible page", async () => {
    renderPage();
    const { dialog } = await openCategory(/in Commit$/);
    const totals = await within(dialog).findByRole("region", { name: "Commit totals" });
    // 20 visible deals of ₹100.00 would sum to ₹2,000.00; the API says 45 deals, ₹4,500.00.
    expect(within(totals).getByText("45")).toBeInTheDocument();
    expect(within(totals).getByText("₹4,500.00")).toBeInTheDocument();
    expect(within(totals).getByText("₹3,375.00")).toBeInTheDocument();
    expect(within(totals).queryByText("₹2,000.00")).not.toBeInTheDocument();
    expect(within(totals).getByText(/Totals cover all 45 deals, not only this page/)).toBeInTheDocument();
    expect(within(dialog).getByText("Showing 1–20 of 45")).toBeInTheDocument();
  });

  it("lists each deal's own figures from the API", async () => {
    dealsMock.mockResolvedValue(
      page(0, 2, {}, [
        deal(1, { name: "Override deal", amount: "333.33", probability: 33, effective_probability: 33, probability_source: "OVERRIDE", weighted_amount: "110.00", stage: "PROPOSAL", owner_name: null, owner_user_id: null, expected_close_date: "2027-01-31" }),
        deal(2, { name: "Default deal" }),
      ]),
    );
    renderPage();
    const { dialog } = await openCategory(/in Commit$/);
    const items = await within(dialog).findAllByRole("listitem");
    const override = within(items[0]!);
    expect(override.getByRole("link", { name: "Override deal" })).toHaveAttribute("href", "/deals/deal-1");
    expect(override.getByText("₹333.33")).toBeInTheDocument();
    expect(override.getByText("INR")).toBeInTheDocument();
    expect(override.getByText("Proposal")).toBeInTheDocument();
    expect(override.getByText("override")).toBeInTheDocument();
    // Effective probability and the stored override are both 33%.
    expect(override.getAllByText("33%")).toHaveLength(2);
    expect(override.getByText("₹110.00")).toBeInTheDocument();
    expect(override.getByText("Jan 31, 2027")).toBeInTheDocument();
    expect(override.getByText("Unassigned")).toBeInTheDocument();

    const fallback = within(items[1]!);
    expect(fallback.getByText("stage default")).toBeInTheDocument();
    expect(fallback.getByText("75%")).toBeInTheDocument();
    expect(fallback.getByText("None")).toBeInTheDocument();
    expect(fallback.getByText("Olivia Owner")).toBeInTheDocument();
  });

  it("narrows to one period and starts again at its first page", async () => {
    renderPage();
    const { user, dialog } = await openCategory(/in Commit$/);
    await within(dialog).findByText("Showing 1–20 of 45");
    await user.click(within(dialog).getByRole("button", { name: "Next page of Commit deals" }));
    await within(dialog).findByText("Showing 21–40 of 45");

    await user.selectOptions(within(dialog).getByLabelText("Period"), "2027-01-01");
    await waitFor(() =>
      expect(lastDealsRequest()?.[0]).toMatchObject({ periodStart: "2027-01-01", offset: 0 }),
    );
    expect(within(dialog).getByText(/expected to close in Q1 2027/)).toBeInTheDocument();
    expect(await within(dialog).findByText("Showing 1–20 of 45")).toBeInTheDocument();
  });

  it("pages through the API with Previous and Next disabled at the ends", async () => {
    renderPage();
    const { user, dialog } = await openCategory(/in Commit$/);
    const previous = await within(dialog).findByRole("button", { name: "Previous page of Commit deals" });
    const next = within(dialog).getByRole("button", { name: "Next page of Commit deals" });
    expect(previous).toBeDisabled();
    await user.click(next);
    await within(dialog).findByText("Showing 21–40 of 45");
    await user.click(next);
    await within(dialog).findByText("Showing 41–45 of 45");
    expect(lastDealsRequest()?.[0]).toMatchObject({ offset: 40, limit: 20 });
    expect(next).toBeDisabled();
    await user.click(previous);
    await within(dialog).findByText("Showing 21–40 of 45");
  });

  it("shows an empty state for a category with no deals", async () => {
    dealsMock.mockResolvedValue(
      page(0, 0, { category: "BEST_CASE", totals: { count: 0, total_amount: "0.00", weighted_amount: "0.00" } }),
    );
    renderPage();
    const { dialog } = await openCategory(/in Best case$/);
    expect(await within(dialog).findByRole("heading", { name: "No Best case deals" })).toBeInTheDocument();
    expect(within(dialog).queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("shows a loading skeleton while the first page loads", async () => {
    dealsMock.mockImplementation(() => new Promise(() => {}));
    renderPage();
    const { dialog } = await openCategory(/in Commit$/);
    expect(within(dialog).getByRole("status")).toHaveTextContent("Loading deals");
    expect(within(dialog).queryByRole("region", { name: "Commit totals" })).not.toBeInTheDocument();
  });

  it("retries a server error, then recovers from the error panel's Retry", async () => {
    dealsMock.mockRejectedValue(new ApiError("boom", 500));
    renderPage();
    const { user, dialog } = await openCategory(/in Commit$/);
    expect(await within(dialog).findByRole("heading", { name: "Deals unavailable" })).toBeInTheDocument();
    // The initial attempt plus the query client's two retries.
    expect(dealsMock).toHaveBeenCalledTimes(3);

    dealsMock.mockImplementation(async ({ offset }) => page(offset, 45));
    await user.click(within(dialog).getByRole("button", { name: "Retry" }));
    expect(await within(dialog).findByText("Showing 1–20 of 45")).toBeInTheDocument();
  });

  it("does not retry a period that left the horizon and says why", async () => {
    dealsMock.mockRejectedValue(new ApiError("period_start must be the start of a period", 422));
    renderPage();
    const { dialog } = await openCategory(/in Commit$/);
    expect(await within(dialog).findByText(/no longer in the forecast horizon/)).toBeInTheDocument();
    expect(dealsMock).toHaveBeenCalledTimes(1);
  });

  it("closes with Escape and returns focus to the category that opened it", async () => {
    renderPage();
    const { user, trigger } = await openCategory(/in Commit$/);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("closes when the horizon changes, so it never shows another horizon's deals", async () => {
    renderPage();
    await openCategory(/in Commit$/);
    act(() => {
      currentSearch = "granularity=month";
      for (const listener of listeners) listener();
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("refetches the forecast and the open drill-down after a deal is changed", async () => {
    renderPage();
    const { dialog } = await openCategory(/in Commit$/);
    await within(dialog).findByText("Showing 1–20 of 45");
    expect(forecastMock).toHaveBeenCalledTimes(1);
    expect(dealsMock).toHaveBeenCalledTimes(1);

    forecastMock.mockResolvedValue(
      forecast({ in_horizon_open: { ...open({ COMMIT: [46, "4600.00", "3450.00"] }), count: 46, total_amount: "4600.00", weighted_amount: "3450.00" } }),
    );
    dealsMock.mockImplementation(async ({ offset }) =>
      page(offset, 46, { totals: { count: 46, total_amount: "4600.00", weighted_amount: "3450.00" } }),
    );
    act(() => notifyDealsChanged());

    await waitFor(() => expect(forecastMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(dealsMock).toHaveBeenCalledTimes(2));
    const totals = within(dialog).getByRole("region", { name: "Commit totals" });
    expect(await within(totals).findByText("₹4,600.00")).toBeInTheDocument();
  });

  it("refetches a cached drill-down the next time it is opened after a deal change", async () => {
    renderPage();
    const { user, dialog } = await openCategory(/in Commit$/);
    await within(dialog).findByText("Showing 1–20 of 45");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    act(() => notifyDealsChanged());
    await openCategory(/in Commit$/);
    await waitFor(() => expect(dealsMock).toHaveBeenCalledTimes(2));
  });

  it("aborts the request for a period the user has moved away from", async () => {
    const signals: AbortSignal[] = [];
    dealsMock.mockImplementation(
      (_params, options) =>
        new Promise((_resolve, reject) => {
          if (options?.signal) signals.push(options.signal);
          options?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        }),
    );
    renderPage();
    const { user, dialog } = await openCategory(/in Commit$/);
    await waitFor(() => expect(signals).toHaveLength(1));
    await user.selectOptions(within(dialog).getByLabelText("Period"), "2027-01-01");
    await waitFor(() => expect(signals).toHaveLength(2));
    // The whole-horizon request is cancelled once its panel body unmounts.
    await waitFor(() => expect(signals[0]?.aborted).toBe(true));
  });
});

describe("correctedOffset", () => {
  it("leaves pages with deals, the first page and placeholders of other offsets alone", () => {
    expect(correctedOffset(page(20, 21), 20)).toBeNull();
    expect(correctedOffset(page(0, 0), 0)).toBeNull();
    expect(correctedOffset(page(20, 20), 40)).toBeNull();
  });

  it("moves an empty page past the end to the new last page, or the first when none are left", () => {
    expect(correctedOffset(page(20, 20), 20)).toBe(0);
    expect(correctedOffset(page(40, 40), 40)).toBe(20);
    expect(correctedOffset(page(60, 41), 60)).toBe(40);
    expect(correctedOffset(page(40, 0), 40)).toBe(0);
  });

  it("never returns the same or a later offset, so it cannot loop", () => {
    // An empty page that claims more deals than its offset (not something the API sends).
    expect(correctedOffset(page(20, 50, {}, []), 20)).toBeNull();
  });
});

describe("Forecast category drill-down: a page emptied by a deal change", () => {
  let total = 0;
  let failing: (offset: number) => boolean = () => false;

  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "";
    failing = () => false;
    forecastMock.mockResolvedValue(forecast());
    dealsMock.mockImplementation(async ({ offset }) => {
      if (failing(offset)) throw new ApiError("boom", 500);
      return page(offset, total);
    });
  });

  /** Records whether text matching the pattern was ever on screen, however briefly. */
  function watchFor(pattern: RegExp) {
    const seen = { value: false };
    const observer = new MutationObserver(() => {
      if (pattern.test(document.body.textContent ?? "")) seen.value = true;
    });
    observer.observe(document.body, { subtree: true, childList: true, characterData: true });
    return { seen, stop: () => observer.disconnect() };
  }

  /** Opens Commit and pages forward until `showing` is on screen. */
  async function openOnPage(pages: number, showing: string) {
    renderPage();
    const opened = await openCategory(/in Commit$/);
    await within(opened.dialog).findByText(/^Showing 1–/);
    for (let index = 1; index < pages; index += 1) {
      await opened.user.click(within(opened.dialog).getByRole("button", { name: "Next page of Commit deals" }));
      await within(opened.dialog).findByText(new RegExp(`^Showing ${index * 20 + 1}–`));
    }
    expect(within(opened.dialog).getByText(showing)).toBeInTheDocument();
    return opened;
  }

  /** Offsets requested since `mark`, in order. */
  function offsetsSince(mark: number) {
    return dealsMock.mock.calls.slice(mark).map(([params]) => params.offset);
  }

  async function changeDeals(nextTotal: number) {
    total = nextTotal;
    const mark = dealsMock.mock.calls.length;
    act(() => notifyDealsChanged());
    return mark;
  }

  it("moves to the previous page when the last page's only deal disappears", async () => {
    total = 21;
    const { dialog } = await openOnPage(2, "Showing 21–21 of 21");
    const misleading = watchFor(/Showing 21–20|No Commit deals/);
    const mark = await changeDeals(20);

    expect(await within(dialog).findByText("Showing 1–20 of 20")).toBeInTheDocument();
    misleading.stop();
    expect(misleading.seen.value).toBe(false);
    // One refetch of the emptied page, one of the corrected page: no loop, no duplicates.
    expect(offsetsSince(mark)).toEqual([20, 0]);
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(20);
    expect(within(dialog).getByRole("button", { name: "Next page of Commit deals" })).toBeDisabled();
  });

  it("moves to the new last page when every deal on the last page disappears", async () => {
    total = 45;
    const { dialog } = await openOnPage(3, "Showing 41–45 of 45");
    const misleading = watchFor(/Showing 41–40|No Commit deals/);
    const mark = await changeDeals(40);

    expect(await within(dialog).findByText("Showing 21–40 of 40")).toBeInTheDocument();
    misleading.stop();
    expect(misleading.seen.value).toBe(false);
    expect(offsetsSince(mark)).toEqual([40, 20]);
  });

  it("shows the empty state and returns to the first page when no deals are left", async () => {
    total = 21;
    const { dialog } = await openOnPage(2, "Showing 21–21 of 21");
    const mark = await changeDeals(0);

    expect(await within(dialog).findByRole("heading", { name: "No Commit deals" })).toBeInTheDocument();
    expect(offsetsSince(mark)).toEqual([20, 0]);
    expect(within(dialog).queryByRole("navigation")).not.toBeInTheDocument();
    const totals = within(dialog).getByRole("region", { name: "Commit totals" });
    expect(within(totals).getByText("0")).toBeInTheDocument();

    // Deals coming back start from the first page, not the old offset.
    const again = await changeDeals(3);
    expect(await within(dialog).findByText("Showing 1–3 of 3")).toBeInTheDocument();
    expect(offsetsSince(again)).toEqual([0]);
  });

  it("stays on a last page that still has deals when the total shrinks", async () => {
    total = 45;
    const { dialog } = await openOnPage(3, "Showing 41–45 of 45");
    const mark = await changeDeals(42);

    expect(await within(dialog).findByText("Showing 41–42 of 42")).toBeInTheDocument();
    expect(offsetsSince(mark)).toEqual([40]);
  });

  it("corrects once and then settles without further requests", async () => {
    total = 21;
    const { dialog } = await openOnPage(2, "Showing 21–21 of 21");
    const mark = await changeDeals(20);
    await within(dialog).findByText("Showing 1–20 of 20");
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(offsetsSince(mark)).toEqual([20, 0]);
  });

  it("keeps normal paging after a correction, with the dialog, category and period unchanged", async () => {
    total = 45;
    const { user, dialog } = await openOnPage(3, "Showing 41–45 of 45");
    await changeDeals(40);
    await within(dialog).findByText("Showing 21–40 of 40");

    expect(screen.getByRole("dialog")).toBe(dialog);
    expect(within(dialog).getByRole("heading", { name: "Commit deals" })).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Period")).toHaveValue("");
    expect(dealsMock.mock.calls.at(-1)?.[0]).toMatchObject({ category: "COMMIT", periodStart: null });

    await user.click(within(dialog).getByRole("button", { name: "Previous page of Commit deals" }));
    expect(await within(dialog).findByText("Showing 1–20 of 40")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Next page of Commit deals" }));
    expect(await within(dialog).findByText("Showing 21–40 of 40")).toBeInTheDocument();
  });

  it("starts a newly selected period or category at its first page", async () => {
    total = 45;
    const { user, dialog } = await openOnPage(3, "Showing 41–45 of 45");
    await user.selectOptions(within(dialog).getByLabelText("Period"), "2027-01-01");
    await waitFor(() =>
      expect(dealsMock.mock.calls.at(-1)?.[0]).toMatchObject({ periodStart: "2027-01-01", offset: 0 }),
    );
    await within(dialog).findByText("Showing 1–20 of 45");

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await user.click(await categoryButton(/in Pipeline$/));
    await waitFor(() =>
      expect(dealsMock.mock.calls.at(-1)?.[0]).toMatchObject({ category: "PIPELINE", periodStart: null, offset: 0 }),
    );
  });

  it("keeps the current page and offset when its refresh fails", async () => {
    total = 21;
    const { user, dialog } = await openOnPage(2, "Showing 21–21 of 21");
    failing = () => true;
    const mark = await changeDeals(21);

    expect(await within(dialog).findByText(/Could not refresh/)).toBeInTheDocument();
    expect(within(dialog).getByText("Showing 21–21 of 21")).toBeInTheDocument();
    // The initial attempt and two retries, all for the same page.
    expect(offsetsSince(mark)).toEqual([20, 20, 20]);

    failing = () => false;
    await user.click(within(dialog).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(offsetsSince(mark)).toEqual([20, 20, 20, 20]));
    expect(within(dialog).getByText("Showing 21–21 of 21")).toBeInTheDocument();
  });

  it("shows an error, not an empty or outdated page, when the corrected page fails to load", async () => {
    total = 21;
    const { user, dialog } = await openOnPage(2, "Showing 21–21 of 21");
    const misleading = watchFor(/Showing 21–20|No Commit deals/);
    failing = (offset) => offset === 0;
    const mark = await changeDeals(20);

    expect(await within(dialog).findByRole("heading", { name: "Deals unavailable" })).toBeInTheDocument();
    // The cached first page predates the change, so it is never shown as current.
    expect(within(dialog).queryByText(/^Showing/)).not.toBeInTheDocument();
    expect(offsetsSince(mark)).toEqual([20, 0, 0, 0]);

    failing = () => false;
    await user.click(within(dialog).getByRole("button", { name: "Retry" }));
    expect(await within(dialog).findByText("Showing 1–20 of 20")).toBeInTheDocument();
    misleading.stop();
    expect(misleading.seen.value).toBe(false);
    expect(offsetsSince(mark)).toEqual([20, 0, 0, 0, 0]);
  });
});

