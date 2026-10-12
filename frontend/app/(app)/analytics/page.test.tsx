import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnalyticsPage from "@/app/(app)/analytics/page";
import { getAnalyticsSummary } from "@/lib/api/analytics";
import type { AnalyticsSummary } from "@/types/api";

vi.mock("@/lib/api/analytics", () => ({
  getAnalyticsSummary: vi.fn(),
}));

const getSummaryMock = vi.mocked(getAnalyticsSummary);

function summaryOf(
  overrides: Partial<AnalyticsSummary["totals"]> = {},
): AnalyticsSummary {
  return {
    range_days: 30,
    source: null,
    start: "2026-09-13T00:00:00Z",
    end: "2026-10-12T06:00:00Z",
    totals: {
      leads_created: 12,
      leads_qualified: 5,
      ai_analyses: 8,
      ai_drafts: 4,
      drafts_approved: 3,
      emails_sent: 2,
      customer_replies: 6,
      human_handoffs: 1,
      follow_ups_completed: 7,
      ...overrides,
    },
    daily: [
      { date: "2026-10-11", leads_created: 2, ai_analyses: 1, emails_sent: 0 },
      { date: "2026-10-12", leads_created: 3, ai_analyses: 2, emails_sent: 1 },
    ],
    leads_by_source: [
      { source: "WEBSITE", count: 9 },
      { source: "MANUAL", count: 3 },
    ],
    qualification_outcomes: {
      qualified: 6,
      unqualified: 1,
      needs_more_information: 1,
    },
  };
}

function metricValue(label: string) {
  const card = screen
    .getAllByRole("article")
    .find((item) =>
      within(item).queryByRole("heading", { level: 3, name: label }),
    );
  if (!card) throw new Error(`No metric card for ${label}`);
  return card;
}

describe("Analytics page", () => {
  beforeEach(() => {
    getSummaryMock.mockReset();
    getSummaryMock.mockResolvedValue(summaryOf());
  });

  it("loads the default 30-day summary and shows real totals", async () => {
    render(<AnalyticsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Analytics" }),
    ).toBeVisible();
    expect(getSummaryMock).toHaveBeenCalledWith({
      rangeDays: 30,
      source: null,
    });

    await waitFor(() =>
      expect(
        within(metricValue("Leads created")).getByText("12"),
      ).toBeVisible(),
    );
    expect(within(metricValue("Qualified leads")).getByText("5")).toBeVisible();
    expect(
      within(metricValue("Customer replies")).getByText("6"),
    ).toBeVisible();
    expect(within(metricValue("AI handled")).getByText("12")).toBeVisible();
    expect(within(metricValue("Human handoffs")).getByText("1")).toBeVisible();
  });

  it("keeps appointments honestly unavailable", async () => {
    render(<AnalyticsPage />);
    await waitFor(() => expect(getSummaryMock).toHaveBeenCalled());

    const appointments = metricValue("Appointments");
    expect(within(appointments).getByText("—")).toBeVisible();
    expect(
      within(appointments).getByText(/Needs a calendar integration/),
    ).toBeVisible();
  });

  it("reloads when the date range or source changes", async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);
    await waitFor(() => expect(getSummaryMock).toHaveBeenCalledTimes(1));

    const range = screen.getByRole("combobox", { name: "Date range" });
    const source = screen.getByRole("combobox", { name: "Lead source" });
    expect(range).toBeEnabled();
    expect(source).toBeEnabled();

    await user.selectOptions(range, "7");
    await waitFor(() =>
      expect(getSummaryMock).toHaveBeenLastCalledWith({
        rangeDays: 7,
        source: null,
      }),
    );
    await user.selectOptions(source, "WEBSITE");
    await waitFor(() =>
      expect(getSummaryMock).toHaveBeenLastCalledWith({
        rangeDays: 7,
        source: "WEBSITE",
      }),
    );
  });

  it("shows breakdowns with rates that never divide by zero", async () => {
    getSummaryMock.mockResolvedValue(
      summaryOf({ ai_drafts: 0, drafts_approved: 0 }),
    );
    render(<AnalyticsPage />);

    const assessment = await screen.findByRole("region", {
      name: "AI lead assessment",
    });
    await waitFor(() =>
      expect(
        within(assessment).getByText("75% of AI assessments"),
      ).toBeVisible(),
    );

    const sources = screen.getByRole("region", { name: "Lead sources" });
    expect(within(sources).getByText("Website")).toBeVisible();
    expect(within(sources).getByText("75% of new leads")).toBeVisible();

    const replies = screen.getByRole("region", {
      name: "Replies and approvals",
    });
    expect(within(replies).getByText("— of drafts")).toBeVisible();
    expect(screen.queryByText(/NaN|Infinity/)).not.toBeInTheDocument();
  });

  it("shows an empty state when nothing happened", async () => {
    getSummaryMock.mockResolvedValue({
      ...summaryOf({
        leads_created: 0,
        leads_qualified: 0,
        ai_analyses: 0,
        ai_drafts: 0,
        drafts_approved: 0,
        emails_sent: 0,
        customer_replies: 0,
        human_handoffs: 0,
        follow_ups_completed: 0,
      }),
      daily: [
        {
          date: "2026-10-12",
          leads_created: 0,
          ai_analyses: 0,
          emails_sent: 0,
        },
      ],
      leads_by_source: [],
      qualification_outcomes: {
        qualified: 0,
        unqualified: 0,
        needs_more_information: 0,
      },
    });
    render(<AnalyticsPage />);

    expect(
      await screen.findByText("No new leads in this period."),
    ).toBeVisible();
    expect(
      screen.getByText("No leads, analyses, or emails in this period yet."),
    ).toBeVisible();
  });

  it("offers a retry when loading fails", async () => {
    const user = userEvent.setup();
    getSummaryMock.mockRejectedValueOnce(new Error("offline"));
    render(<AnalyticsPage />);

    expect(
      await screen.findByText("Analytics could not be loaded"),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(
        within(metricValue("Leads created")).getByText("12"),
      ).toBeVisible(),
    );
    expect(getSummaryMock).toHaveBeenCalledTimes(2);
  });
});
