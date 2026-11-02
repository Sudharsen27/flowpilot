import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ForecastAccuracyPage from "@/app/(app)/forecast/accuracy/page";
import { QueryProvider } from "@/components/providers/query-provider";
import { ApiError } from "@/lib/api/client";
import { getForecastAccuracy } from "@/lib/api/pipeline";
import { notifyDealsChanged, notifySalesTargetsChanged } from "@/lib/deal-events";
import { createQueryClient } from "@/lib/query-client";
import { ACCURACY_SUMMARY, accuracyFixture } from "@/test/forecast-accuracy-fixtures";

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
    usePathname: () => "/forecast/accuracy",
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

vi.mock("@/lib/api/pipeline", () => ({ getForecastAccuracy: vi.fn() }));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    session: {
      user: { id: "user-1", name: "Rita Rep", email: "r@example.com" },
      organization: { id: "org-1", name: "Acme", slug: "acme" },
      membership: { role: "MEMBER" },
    },
    isLoading: false,
  }),
}));

const accuracyMock = vi.mocked(getForecastAccuracy);
const ALL_LEADS = [0, 30, 60, 90];

function renderPage() {
  return render(
    <QueryProvider client={createQueryClient({ retryDelay: 0 })}>
      <ForecastAccuracyPage />
    </QueryProvider>,
  );
}

function requested(fromMonth: string | null, toMonth: string | null) {
  return [{ fromMonth, toMonth, leadDays: ALL_LEADS }, { signal: expect.any(AbortSignal) }] as const;
}

/** A summary card's value and text, by its heading. */
function card(label: string) {
  const heading = screen.getByRole("heading", { name: label, level: 3 });
  const article = heading.closest("article");
  if (!article) throw new Error(`No card for ${label}`);
  return article;
}

/** The default summary (month start, projected) has rendered. */
async function loaded() {
  await waitFor(() => expect(within(card("Weighted accuracy")).getByText("80.0%")).toBeInTheDocument());
}

function leadsTable() {
  return within(screen.getByRole("region", { name: "Accuracy by lead time" })).getByRole("table");
}

describe("forecast accuracy page", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-02T06:30:00Z"));
    currentSearch = "";
    listeners.clear();
    mockReplace.mockReset();
    accuracyMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads the server's default range with every lead and shows the selected summary", async () => {
    let resolve: (value: ReturnType<typeof accuracyFixture>) => void = () => undefined;
    accuracyMock.mockReturnValue(new Promise((done) => (resolve = done)));
    renderPage();
    expect(screen.getByText("Loading forecast accuracy")).toBeInTheDocument();
    expect(accuracyMock).toHaveBeenCalledWith(...requested(null, null));

    await act(async () => resolve(accuracyFixture()));
    expect(await screen.findByRole("heading", { name: "Forecast accuracy", level: 1 })).toBeInTheDocument();
    expect(within(card("Weighted accuracy")).getByText("80.0%")).toBeInTheDocument();
    expect(
      within(card("Weighted accuracy")).getByText("2 of 3 months compared; 1 without a saved forecast."),
    ).toBeInTheDocument();
    expect(within(card("Variance (actual − forecast)")).getByLabelText("\u2212₹20,000.00")).toBeInTheDocument();
    expect(within(card("Variance (actual − forecast)")).getByText(/^\u221216\.7% of forecast\./)).toBeInTheDocument();
    expect(within(card("Forecast total (estimate)")).getByLabelText("₹1,20,000.00")).toBeInTheDocument();
    expect(within(card("Actual won (compared months)")).getByLabelText("₹1,00,000.00")).toBeInTheDocument();
    expect(screen.getByText("As of 2026-11-02 06:30:00 UTC")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to forecast" })).toHaveAttribute("href", "/forecast");
  });

  it("explains months before tracking and snapshots in another currency", async () => {
    accuracyMock.mockResolvedValue(accuracyFixture());
    renderPage();
    expect(await screen.findByRole("region", { name: "Some months predate forecast tracking" })).toHaveTextContent(
      "FlowPilot started saving forecasts on 2026-08-25 00:05:00 UTC.",
    );
    expect(screen.getByRole("region", { name: "Some saved forecasts are in another currency" })).toHaveTextContent(
      "1 month has a saved forecast in a currency other than INR.",
    );
  });

  it("switches lead time in the browser, without another request, and never shows 0 for no data", async () => {
    const user = userEvent.setup();
    accuracyMock.mockResolvedValue(accuracyFixture());
    renderPage();
    await loaded();

    await user.click(screen.getByRole("button", { name: "30 days", pressed: false }));
    expect(mockReplace).toHaveBeenLastCalledWith("/forecast/accuracy?lead=30", { scroll: false });
    expect(screen.getByRole("button", { name: "30 days", pressed: true })).toBeInTheDocument();
    for (const label of ["Weighted accuracy", "Variance (actual − forecast)", "Forecast total (estimate)"]) {
      expect(within(card(label)).getByText("—")).toBeInTheDocument();
      expect(
        within(card(label)).getByText("No closed month in this range has a saved forecast at this lead time."),
      ).toBeInTheDocument();
      expect(within(card(label)).queryByText(/₹0|0\.0%/)).not.toBeInTheDocument();
    }
    expect(accuracyMock).toHaveBeenCalledTimes(1);
  });

  it("selects a lead and basis from the lead-time table", async () => {
    const user = userEvent.setup();
    accuracyMock.mockResolvedValue(accuracyFixture());
    renderPage();
    await loaded();

    const table = leadsTable();
    expect(
      within(table).getByRole("button", { name: /^Month start, Projected: weighted accuracy 80\.0%; 2 months$/ }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      within(table).getByRole("button", { name: /^Month start, Best case scenario: weighted accuracy \u2212110\.0%/ }),
    ).toBeInTheDocument();
    expect(
      within(table).getByRole("button", { name: /^90 days before, Commit scenario: weighted accuracy not available; No comparable months$/ }),
    ).toBeInTheDocument();

    await user.click(within(table).getByRole("button", { name: /^Month start, Commit scenario:/ }));
    expect(mockReplace).toHaveBeenLastCalledWith("/forecast/accuracy?basis=COMMIT_SCENARIO", { scroll: false });
    expect(within(card("Weighted accuracy")).getByText("95.0%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Commit scenario", pressed: true })).toBeInTheDocument();
    expect(accuracyMock).toHaveBeenCalledTimes(1);
  });

  it("restores lead and basis from the URL", async () => {
    currentSearch = "lead=0&basis=BEST_CASE_SCENARIO";
    accuracyMock.mockResolvedValue(accuracyFixture());
    renderPage();
    await waitFor(() => expect(within(card("Weighted accuracy")).getByText("\u2212110.0%")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Best case scenario", pressed: true })).toBeInTheDocument();
  });

  it("requests explicit UTC months for other ranges and for the current month", async () => {
    const user = userEvent.setup();
    accuracyMock.mockResolvedValue(accuracyFixture());
    renderPage();
    await loaded();

    await user.selectOptions(screen.getByLabelText("Range"), "12");
    expect(mockReplace).toHaveBeenLastCalledWith("/forecast/accuracy?range=12", { scroll: false });
    await waitFor(() => expect(accuracyMock).toHaveBeenLastCalledWith(...requested("2025-11-01", "2026-10-01")));

    await user.click(screen.getByRole("checkbox", { name: "Include current month" }));
    expect(mockReplace).toHaveBeenLastCalledWith("/forecast/accuracy?range=12&current=1", { scroll: false });
    await waitFor(() => expect(accuracyMock).toHaveBeenLastCalledWith(...requested("2025-11-01", "2026-11-01")));
    expect(accuracyMock).toHaveBeenCalledTimes(3);
  });

  it("explains a missing comparison when no revenue was won", async () => {
    const summary = ACCURACY_SUMMARY.map((entry) =>
      entry.lead_days === 0 && entry.basis === "PROJECTED"
        ? { ...entry, actual_total: "0.00", weighted_accuracy_percent: null, status: "NO_ACTUAL_REVENUE" as const }
        : entry,
    );
    accuracyMock.mockResolvedValue(accuracyFixture({ summary }));
    renderPage();
    const accuracyCard = await waitFor(() => card("Weighted accuracy"));
    expect(
      within(accuracyCard).getByText("No revenue was won in the compared months, so accuracy is undefined."),
    ).toBeInTheDocument();
    expect(within(card("Variance (actual − forecast)")).getByLabelText("\u2212₹20,000.00")).toBeInTheDocument();
  });

  it("shows that tracking has not started when the organization has no snapshots", async () => {
    accuracyMock.mockResolvedValue(
      accuracyFixture({
        first_captured_at: null,
        months: accuracyFixture().months.map((month) => ({
          ...month,
          forecasts: month.forecasts.map((lead) => ({
            ...lead,
            snapshot_status: "BEFORE_FIRST_SNAPSHOT" as const,
            snapshot_date: null,
            captured_at: null,
            comparisons: [],
          })),
        })),
      }),
    );
    renderPage();
    expect(await screen.findByRole("region", { name: "Forecast tracking has not started" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View current forecast" })).toHaveAttribute("href", "/forecast");
    expect(screen.queryByRole("heading", { name: "Weighted accuracy" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Methodology and assumptions" })).toBeInTheDocument();
  });

  it.each([
    [403, "You do not have access to this organization's forecast."],
    [404, "Forecast accuracy is not available on this server yet. Try again once the server has been updated."],
    [422, "This range is not supported. Choose a different range."],
    [500, "Forecast accuracy could not be loaded. Your deals are unaffected."],
  ])("explains a %i and retries on request", async (status, message) => {
    const user = userEvent.setup();
    accuracyMock.mockRejectedValue(new ApiError(`Request failed: ${status}`, status));
    renderPage();
    const panel = await screen.findByRole("region", { name: "Forecast accuracy unavailable" });
    expect(panel).toHaveTextContent(message);
    const calls = accuracyMock.mock.calls.length;

    accuracyMock.mockResolvedValue(accuracyFixture());
    await user.click(within(panel).getByRole("button", { name: "Retry" }));
    await loaded();
    expect(accuracyMock.mock.calls.length).toBe(calls + 1);
  });

  it("refreshes after a deal write, but not after a sales target save", async () => {
    accuracyMock.mockResolvedValue(accuracyFixture());
    renderPage();
    await loaded();
    expect(accuracyMock).toHaveBeenCalledTimes(1);

    act(() => notifySalesTargetsChanged());
    await act(async () => {
      await Promise.resolve();
    });
    expect(accuracyMock).toHaveBeenCalledTimes(1);

    act(() => notifyDealsChanged());
    await waitFor(() => expect(accuracyMock).toHaveBeenCalledTimes(2));
  });
});
