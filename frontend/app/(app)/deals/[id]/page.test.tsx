import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DealDetailPage from "@/app/(app)/deals/[id]/page";
import { ToastProvider } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import {
  changeDealStage,
  correctWonDealAmount,
  getDeal,
  getDealHistory,
  updateDeal,
} from "@/lib/api/deals";
import { listOrganizationMembers } from "@/lib/api/organizations";
import type { Deal, DealHistoryEvent, MemberPublic } from "@/types/api";

const authMock = vi.hoisted(() => ({ role: "OWNER" as string }));

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "deal-1" }) }));
vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    session: {
      user: { id: "user-owner", name: "Olivia Owner", email: "o@example.com" },
      organization: { id: "org-1", name: "Acme", slug: "acme" },
      membership: { role: authMock.role },
    },
    isLoading: false,
  }),
}));
vi.mock("@/lib/api/deals", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/deals")>();
  return {
    ...actual,
    getDeal: vi.fn(),
    getDealHistory: vi.fn(),
    updateDeal: vi.fn(),
    changeDealStage: vi.fn(),
    correctWonDealAmount: vi.fn(),
  };
});
vi.mock("@/lib/api/organizations", () => ({ listOrganizationMembers: vi.fn() }));
vi.mock("@/lib/api/leads", () => ({ getLeads: vi.fn() }));

const getDealMock = vi.mocked(getDeal);
const historyMock = vi.mocked(getDealHistory);
const updateMock = vi.mocked(updateDeal);
const stageMock = vi.mocked(changeDealStage);
const correctMock = vi.mocked(correctWonDealAmount);

const members: MemberPublic[] = [
  { membership_id: "m-1", role: "OWNER", user: { id: "user-owner", name: "Olivia Owner", email: "o@example.com" } },
  { membership_id: "m-2", role: "MEMBER", user: { id: "user-member", name: "Max Member", email: "m@example.com" } },
];

function deal(overrides: Partial<Deal> = {}): Deal {
  return {
    id: "deal-1",
    name: "Acme expansion",
    description: "Platform upsell",
    amount: "125000.50",
    currency: "INR",
    stage: "PROPOSAL",
    probability: 65,
    effective_probability: 65,
    probability_source: "OVERRIDE",
    forecast_category: "PIPELINE",
    expected_close_date: "2026-12-15",
    closed_at: null,
    owner_user_id: "user-owner",
    owner_name: "Olivia Owner",
    lead_id: "lead-1",
    lead_name: "Ada Prospect",
    lost_reason: null,
    revision: 3,
    stage_entered_at: "2026-10-20T10:00:00Z",
    created_at: "2026-10-01T10:00:00Z",
    updated_at: "2026-10-28T10:00:00Z",
    ...overrides,
  };
}

const history: DealHistoryEvent[] = [
  {
    id: "e1",
    deal_id: "deal-1",
    changes: ["CREATED"],
    previous_stage: null,
    new_stage: "QUALIFICATION",
    previous_amount: null,
    new_amount: "100000.00",
    previous_expected_close_date: null,
    new_expected_close_date: "2026-12-01",
    changed_by_user_id: "user-owner",
    changed_by_name: "Olivia Owner",
    change_reason: null,
    created_at: "2026-10-01T10:00:00Z",
  },
  {
    id: "e2",
    deal_id: "deal-1",
    changes: ["AMOUNT", "EXPECTED_CLOSE_DATE"],
    previous_stage: "QUALIFICATION",
    new_stage: "QUALIFICATION",
    previous_amount: "100000.00",
    new_amount: "125000.50",
    previous_expected_close_date: "2026-12-01",
    new_expected_close_date: "2026-12-15",
    changed_by_user_id: null,
    changed_by_name: null,
    change_reason: "Scope grew",
    created_at: "2026-10-10T10:00:00Z",
  },
  {
    id: "e3",
    deal_id: "deal-1",
    changes: ["STAGE"],
    previous_stage: "QUALIFICATION",
    new_stage: "PROPOSAL",
    previous_amount: "125000.50",
    new_amount: "125000.50",
    previous_expected_close_date: "2026-12-15",
    new_expected_close_date: "2026-12-15",
    changed_by_user_id: "user-owner",
    changed_by_name: "Olivia Owner",
    change_reason: null,
    created_at: "2026-10-20T10:00:00Z",
  },
];

function renderPage() {
  return render(
    <ToastProvider>
      <DealDetailPage />
    </ToastProvider>,
  );
}

describe("Deal detail page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.role = "OWNER";
    getDealMock.mockResolvedValue(deal());
    historyMock.mockResolvedValue({ items: history, limit: 200, offset: 0, total: 3 });
    vi.mocked(listOrganizationMembers).mockResolvedValue(members);
  });

  it("shows deal details and chronological history", async () => {
    renderPage();
    expect(screen.getByText("Loading deal", { selector: ".sr-only" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1, name: "Acme expansion" })).toBeVisible();
    const details = screen.getByRole("region", { name: "Deal details" });
    expect(within(details).getByText("₹1,25,000.50")).toBeInTheDocument();
    expect(within(details).getByText("65%")).toBeInTheDocument();
    expect(within(details).getByText("override")).toBeInTheDocument();
    expect(within(details).getByText("Dec 15, 2026")).toBeInTheDocument();
    expect(within(details).getByRole("link", { name: "Ada Prospect" })).toHaveAttribute(
      "href",
      "/leads/lead-1",
    );
    expect(within(details).getByText("#3")).toBeInTheDocument();
    const timeline = await screen.findByRole("list", { name: "Deal history, oldest first" });
    const entries = within(timeline).getAllByRole("listitem").filter((item) => item.parentElement === timeline);
    expect(entries).toHaveLength(3);
    expect(entries[0]).toHaveTextContent("Created in Qualification at ₹1,00,000.00, closing Dec 1, 2026.");
    expect(entries[1]).toHaveTextContent("Amount changed from ₹1,00,000.00 to ₹1,25,000.50.");
    expect(entries[1]).toHaveTextContent("Expected close moved from Dec 1, 2026 to Dec 15, 2026.");
    expect(entries[1]).toHaveTextContent("Reason: Scope grew");
    expect(entries[1]).toHaveTextContent("by a former member");
    expect(entries[2]).toHaveTextContent("Stage moved from Qualification to Proposal.");
    expect(historyMock).toHaveBeenCalledWith("deal-1", { limit: 200 });
  });

  it("explains a missing deal and retries other failures", async () => {
    const user = userEvent.setup();
    getDealMock.mockRejectedValueOnce(new ApiError("Request failed: 404", 404));
    const { unmount } = renderPage();
    expect(await screen.findByText("This deal could not be found.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    unmount();

    getDealMock.mockRejectedValueOnce(new Error("network"));
    renderPage();
    expect(await screen.findByText("Unable to load this deal")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Acme expansion" })).toBeVisible();
  });

  it("edits only changed fields with the current revision", async () => {
    const user = userEvent.setup();
    updateMock.mockResolvedValue(deal({ amount: "150000.00", revision: 4 }));
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit deal" });
    expect(within(dialog).getByLabelText("Stage")).toBeDisabled();
    const amount = within(dialog).getByLabelText(/Amount/);
    await user.clear(amount);
    await user.type(amount, "150000");
    await user.type(within(dialog).getByLabelText("Reason for change"), "Bigger scope");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect(updateMock).toHaveBeenCalledWith("deal-1", {
      expected_revision: 3,
      amount: "150000",
      change_reason: "Bigger scope",
    });
    expect(await screen.findByText("Deal updated")).toBeInTheDocument();
    await waitFor(() => expect(historyMock).toHaveBeenCalledTimes(2));
  });

  it("shows the forecast category and changes only it", async () => {
    const user = userEvent.setup();
    updateMock.mockResolvedValue(deal({ forecast_category: "BEST_CASE", revision: 4 }));
    renderPage();
    const label = await screen.findByText("Forecast category", { selector: "dt" });
    expect(label.nextElementSibling).toHaveTextContent("Pipeline");
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit deal" });
    await user.selectOptions(within(dialog).getByLabelText("Forecast category"), "BEST_CASE");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect(updateMock).toHaveBeenCalledWith("deal-1", {
      expected_revision: 3,
      forecast_category: "BEST_CASE",
    });
  });

  it("does not resend an unchanged amount written differently", async () => {
    const user = userEvent.setup();
    updateMock.mockResolvedValue(deal({ name: "Renamed", revision: 4 }));
    getDealMock.mockResolvedValue(deal({ amount: "125000.50" }));
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit deal" });
    const amount = within(dialog).getByLabelText(/Amount/);
    await user.clear(amount);
    await user.type(amount, "125,000.500");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
    // "125,000.500" has three decimals, so it is rejected locally instead.
    expect(within(dialog).getByText("Use at most 2 decimal places.")).toBeInTheDocument();
    await user.clear(amount);
    await user.type(amount, "125000.5");
    const name = within(dialog).getByLabelText(/Deal name/);
    await user.clear(name);
    await user.type(name, "Renamed");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect(updateMock).toHaveBeenCalledWith("deal-1", { expected_revision: 3, name: "Renamed" });
  });

  it("reloads the latest deal on a revision conflict instead of overwriting it", async () => {
    const user = userEvent.setup();
    updateMock.mockRejectedValueOnce(
      new ApiError("Request failed: 409", 409, {
        detail: "This deal changed. Refresh and review the latest version.",
        current_revision: 4,
      }),
    );
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit deal" });
    getDealMock.mockResolvedValue(deal({ amount: "999.00", name: "Changed elsewhere", revision: 4 }));
    const name = within(dialog).getByLabelText(/Deal name/);
    await user.clear(name);
    await user.type(name, "My rename");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));

    expect(
      await within(dialog).findByText(/Someone else changed this deal\. We loaded the latest version/),
    ).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/Deal name/)).toHaveValue("Changed elsewhere");
    expect(within(dialog).getByLabelText(/Amount/)).toHaveValue("999.00");
    expect(updateMock).toHaveBeenCalledTimes(1);
    // The page behind the open modal is hidden from assistive tech but already refreshed.
    expect(
      await screen.findByRole("heading", { level: 1, name: "Changed elsewhere", hidden: true }),
    ).toBeInTheDocument();

    updateMock.mockResolvedValueOnce(deal({ name: "My rename", revision: 5 }));
    await user.clear(within(dialog).getByLabelText(/Deal name/));
    await user.type(within(dialog).getByLabelText(/Deal name/), "My rename");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect(updateMock).toHaveBeenLastCalledWith("deal-1", {
      expected_revision: 4,
      name: "My rename",
    });
  });

  it("lets owners reassign but shows members a read-only owner", async () => {
    const user = userEvent.setup();
    updateMock.mockResolvedValue(deal({ owner_user_id: "user-member", owner_name: "Max Member", revision: 4 }));
    const { unmount } = renderPage();
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    let dialog = await screen.findByRole("dialog", { name: "Edit deal" });
    await screen.findByRole("option", { name: "Max Member" });
    await user.selectOptions(within(dialog).getByLabelText("Owner"), "user-member");
    await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect(updateMock).toHaveBeenCalledWith("deal-1", {
      expected_revision: 3,
      owner_user_id: "user-member",
    });
    unmount();

    authMock.role = "MEMBER";
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    dialog = await screen.findByRole("dialog", { name: "Edit deal" });
    expect(within(dialog).getByLabelText("Owner")).toBeDisabled();
    expect(within(dialog).getByText("Only owners and admins can reassign deals.")).toBeInTheDocument();
  });

  it("moves between open stages with an optional new override", async () => {
    const user = userEvent.setup();
    stageMock.mockResolvedValue(
      deal({ stage: "NEGOTIATION", probability: null, effective_probability: 75, probability_source: "STAGE_DEFAULT", revision: 4 }),
    );
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Change stage" }));
    const dialog = await screen.findByRole("dialog", { name: "Change stage" });
    const stageSelect = within(dialog).getByLabelText(/New stage/);
    expect(within(stageSelect).queryByRole("option", { name: "Proposal" })).not.toBeInTheDocument();
    await user.selectOptions(stageSelect, "NEGOTIATION");
    expect(within(dialog).getByText(/Any existing override is cleared on a stage change/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Move to Negotiation" }));
    expect(stageMock).toHaveBeenCalledWith("deal-1", {
      stage: "NEGOTIATION",
      expected_revision: 3,
      probability: null,
      lost_reason: null,
      change_reason: null,
    });
    expect(await screen.findByText("Stage changed")).toBeInTheDocument();
    const details = screen.getByRole("region", { name: "Deal details" });
    expect(within(details).getByText("75%")).toBeInTheDocument();
    expect(within(details).getByText("stage default")).toBeInTheDocument();
  });

  it("confirms closing as won and requires a reason to close as lost", async () => {
    const user = userEvent.setup();
    stageMock.mockResolvedValue(deal({ stage: "CLOSED_LOST", lost_reason: "Budget cut", revision: 4 }));
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Change stage" }));
    const dialog = await screen.findByRole("dialog", { name: "Change stage" });
    await user.selectOptions(within(dialog).getByLabelText(/New stage/), "CLOSED_WON");
    expect(within(dialog).getByText(/Marking this deal as won closes it/)).toBeInTheDocument();
    expect(within(dialog).queryByLabelText(/Probability override/)).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Mark as won" })).toBeInTheDocument();

    await user.selectOptions(within(dialog).getByLabelText(/New stage/), "CLOSED_LOST");
    await user.click(within(dialog).getByRole("button", { name: "Mark as lost" }));
    expect(within(dialog).getByText("Explain why the deal was lost.")).toBeInTheDocument();
    expect(stageMock).not.toHaveBeenCalled();
    await user.type(within(dialog).getByLabelText(/Lost reason/), "Budget cut");
    await user.click(within(dialog).getByRole("button", { name: "Mark as lost" }));
    expect(stageMock).toHaveBeenCalledWith(
      "deal-1",
      expect.objectContaining({ stage: "CLOSED_LOST", lost_reason: "Budget cut", probability: null }),
    );
  });

  it("does not change the stage when the deal changed elsewhere", async () => {
    const user = userEvent.setup();
    stageMock.mockRejectedValueOnce(new ApiError("Request failed: 409", 409, { current_revision: 4 }));
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Change stage" }));
    const dialog = await screen.findByRole("dialog", { name: "Change stage" });
    getDealMock.mockResolvedValue(deal({ stage: "NEGOTIATION", revision: 4 }));
    await user.selectOptions(within(dialog).getByLabelText(/New stage/), "DISCOVERY");
    await user.click(within(dialog).getByRole("button", { name: "Move to Discovery" }));
    expect(
      await within(dialog).findByText(/Someone else changed this deal, so the stage was not changed/),
    ).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/New stage/)).toHaveValue("");
    expect(within(dialog).getByText(/is in Negotiation/)).toBeInTheDocument();
  });

  it("keeps the deal visible when only history fails", async () => {
    const user = userEvent.setup();
    historyMock.mockRejectedValueOnce(new Error("network"));
    renderPage();
    expect(await screen.findByText("History could not be loaded")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Acme expansion" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry history" }));
    expect(await screen.findByRole("list", { name: "Deal history, oldest first" })).toBeInTheDocument();
  });

  describe("won deals", () => {
    const won = () =>
      deal({
        stage: "CLOSED_WON",
        amount: "120000.00",
        probability: null,
        effective_probability: 100,
        probability_source: "STAGE_DEFAULT",
        forecast_category: null,
        closed_at: "2026-10-25T10:00:00Z",
      });

    beforeEach(() => {
      getDealMock.mockResolvedValue(won());
    });

    it("shows a won deal as Closed and never sends a category for it", async () => {
      const user = userEvent.setup();
      updateMock.mockResolvedValue({ ...won(), name: "Renamed", revision: 4 });
      renderPage();
      const label = await screen.findByText("Forecast category", { selector: "dt" });
      expect(label.nextElementSibling).toHaveTextContent("Closed");
      await user.click(screen.getByRole("button", { name: "Edit" }));
      const dialog = await screen.findByRole("dialog", { name: "Edit deal" });
      const category = within(dialog).getByLabelText("Forecast category");
      expect(category).toBeDisabled();
      expect(category).toHaveDisplayValue("Closed");
      const name = within(dialog).getByLabelText(/Deal name/);
      await user.clear(name);
      await user.type(name, "Renamed");
      await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
      expect(updateMock).toHaveBeenCalledWith("deal-1", { expected_revision: 3, name: "Renamed" });
    });

    it.each(["OWNER", "ADMIN", "MEMBER"])(
      "keeps the amount read-only in the edit form for %s",
      async (role) => {
        const user = userEvent.setup();
        authMock.role = role;
        updateMock.mockResolvedValue({ ...won(), name: "Renamed", revision: 4 });
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Edit" }));
        const dialog = await screen.findByRole("dialog", { name: "Edit deal" });
        const amount = within(dialog).getByLabelText(/Amount/);
        expect(amount).toHaveAttribute("readonly");
        expect(amount).toHaveAccessibleDescription(
          role === "MEMBER"
            ? "Won amounts are locked. An owner or admin can record a correction."
            : "Won amounts are locked. Use Correct amount on the deal page to record a change with a reason.",
        );
        await user.type(amount, "5");
        expect(amount).toHaveValue("120000.00");
        const name = within(dialog).getByLabelText(/Deal name/);
        await user.clear(name);
        await user.type(name, "Renamed");
        await user.click(within(dialog).getByRole("button", { name: "Save changes" }));
        expect(updateMock).toHaveBeenCalledWith("deal-1", { expected_revision: 3, name: "Renamed" });
      },
    );

    it.each(["OWNER", "ADMIN"])(
      "lets %s record an audited correction with a required reason",
      async (role) => {
        const user = userEvent.setup();
        authMock.role = role;
        correctMock.mockResolvedValue({ ...won(), amount: "118500.00", revision: 4 });
        renderPage();
        await user.click(await screen.findByRole("button", { name: "Correct amount" }));
        const dialog = await screen.findByRole("dialog", { name: "Correct won amount" });
        expect(within(dialog).getByText(/was won at ₹1,20,000.00/)).toBeInTheDocument();
        const amount = within(dialog).getByLabelText(/Corrected amount \(INR\)/);
        expect(amount).toHaveValue("120000.00");

        await user.click(within(dialog).getByRole("button", { name: "Record correction" }));
        expect(within(dialog).getByText("Enter an amount different from the current amount.")).toBeInTheDocument();
        expect(within(dialog).getByText("Explain why the amount is being corrected.")).toBeInTheDocument();

        await user.clear(amount);
        await user.type(amount, "12.345");
        await user.type(within(dialog).getByLabelText(/Correction reason/), "   ");
        await user.click(within(dialog).getByRole("button", { name: "Record correction" }));
        expect(within(dialog).getByText("Use at most 2 decimal places.")).toBeInTheDocument();
        expect(within(dialog).getByText("Explain why the amount is being corrected.")).toBeInTheDocument();
        expect(correctMock).not.toHaveBeenCalled();

        await user.clear(amount);
        await user.type(amount, "1,18,500.00");
        await user.clear(within(dialog).getByLabelText(/Correction reason/));
        await user.type(within(dialog).getByLabelText(/Correction reason/), "  Invoice discount  ");
        await user.click(within(dialog).getByRole("button", { name: "Record correction" }));
        expect(correctMock).toHaveBeenCalledWith("deal-1", {
          expected_revision: 3,
          amount: "118500.00",
          reason: "Invoice discount",
        });
        expect(await screen.findByText("Amount corrected")).toBeInTheDocument();
        await waitFor(() => expect(historyMock).toHaveBeenCalledTimes(2));
        const details = screen.getByRole("region", { name: "Deal details" });
        expect(within(details).getByText("₹1,18,500.00")).toBeInTheDocument();
      },
    );

    it("shows members no correction or stage controls on a won deal", async () => {
      authMock.role = "MEMBER";
      renderPage();
      await screen.findByRole("heading", { level: 1, name: "Acme expansion" });
      expect(screen.queryByRole("button", { name: "Correct amount" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Change stage" })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
      expect(screen.getByRole("note")).toHaveTextContent(
        "Only owners and admins can reopen or change a won deal.",
      );
    });

    it("offers corrections only on won deals", async () => {
      getDealMock.mockResolvedValue(deal());
      renderPage();
      await screen.findByRole("heading", { level: 1, name: "Acme expansion" });
      expect(screen.queryByRole("button", { name: "Correct amount" })).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Change stage" })).toBeInTheDocument();
      expect(screen.queryByRole("note")).not.toBeInTheDocument();
    });

    it("handles correction conflicts, permission and validation errors", async () => {
      const user = userEvent.setup();
      correctMock.mockRejectedValueOnce(
        new ApiError("Request failed: 409", 409, { current_revision: 4 }),
      );
      renderPage();
      await user.click(await screen.findByRole("button", { name: "Correct amount" }));
      const dialog = await screen.findByRole("dialog", { name: "Correct won amount" });
      const amount = within(dialog).getByLabelText(/Corrected amount/);
      await user.clear(amount);
      await user.type(amount, "100000");
      await user.type(within(dialog).getByLabelText(/Correction reason/), "Credit note");
      getDealMock.mockResolvedValue({ ...won(), amount: "119000.00", revision: 4 });
      await user.click(within(dialog).getByRole("button", { name: "Record correction" }));
      expect(
        await within(dialog).findByText(/Someone else changed this deal, so the correction was not saved/),
      ).toBeInTheDocument();
      expect(amount).toHaveValue("119000.00");

      correctMock.mockRejectedValueOnce(
        new ApiError("Request failed: 403", 403, {
          detail: "Only owners and admins can correct a won deal amount",
        }),
      );
      await user.clear(amount);
      await user.type(amount, "100000");
      await user.click(within(dialog).getByRole("button", { name: "Record correction" }));
      expect(
        await within(dialog).findByText("Only owners and admins can correct a won deal amount"),
      ).toBeInTheDocument();
      expect(correctMock).toHaveBeenLastCalledWith("deal-1", {
        expected_revision: 4,
        amount: "100000",
        reason: "Credit note",
      });

      correctMock.mockRejectedValueOnce(
        new ApiError("Request failed: 422", 422, {
          detail: [{ loc: ["body", "amount"], msg: "Input should be less than or equal to 999999999999.99" }],
        }),
      );
      await user.click(within(dialog).getByRole("button", { name: "Record correction" }));
      expect(
        await within(dialog).findByText("Input should be less than or equal to 999999999999.99"),
      ).toBeInTheDocument();

      correctMock.mockRejectedValueOnce(
        new ApiError("Request failed: 422", 422, {
          detail: "Only won deals use amount corrections; use PATCH",
        }),
      );
      await user.click(within(dialog).getByRole("button", { name: "Record correction" }));
      expect(
        await within(dialog).findByText("Only won deals use amount corrections; use PATCH"),
      ).toBeInTheDocument();
      expect(dialog).toBeInTheDocument();
    });

    it.each(["OWNER", "ADMIN"])("lets %s reopen a won deal", async (role) => {
      const user = userEvent.setup();
      authMock.role = role;
      stageMock.mockResolvedValue(deal({ stage: "NEGOTIATION", revision: 4 }));
      renderPage();
      await user.click(await screen.findByRole("button", { name: "Change stage" }));
      const dialog = await screen.findByRole("dialog", { name: "Change stage" });
      await user.selectOptions(within(dialog).getByLabelText(/New stage/), "NEGOTIATION");
      expect(within(dialog).getByText(/Reopening clears the close date/)).toBeInTheDocument();
      await user.click(within(dialog).getByRole("button", { name: "Move to Negotiation" }));
      expect(stageMock).toHaveBeenCalledWith(
        "deal-1",
        expect.objectContaining({ stage: "NEGOTIATION", expected_revision: 3 }),
      );
    });

    it("shows the API's reason when a stage change is refused", async () => {
      const user = userEvent.setup();
      stageMock.mockRejectedValueOnce(
        new ApiError("Request failed: 403", 403, {
          detail: "Only owners and admins can move a won deal to another stage",
        }),
      );
      renderPage();
      await user.click(await screen.findByRole("button", { name: "Change stage" }));
      const dialog = await screen.findByRole("dialog", { name: "Change stage" });
      await user.selectOptions(within(dialog).getByLabelText(/New stage/), "PROPOSAL");
      await user.click(within(dialog).getByRole("button", { name: "Move to Proposal" }));
      expect(
        await within(dialog).findByText("Only owners and admins can move a won deal to another stage"),
      ).toBeInTheDocument();
    });
  });

  it("shows probability changes and corrections from the history API", async () => {
    historyMock.mockResolvedValue({
      items: [
        ...history,
        {
          ...history[2]!,
          id: "e4",
          changes: ["PROBABILITY"],
          previous_stage: "PROPOSAL",
          previous_probability: null,
          new_probability: 65,
          is_correction: false,
        },
      ],
      limit: 200,
      offset: 0,
      total: 4,
    });
    renderPage();
    const timeline = await screen.findByRole("list", { name: "Deal history, oldest first" });
    const entries = within(timeline).getAllByRole("listitem").filter((item) => item.parentElement === timeline);
    // Rows from before probability history keep rendering as before.
    expect(entries[1]).toHaveTextContent("Amount changed from ₹1,00,000.00 to ₹1,25,000.50.");
    expect(entries[3]).toHaveTextContent(
      "Probability changed from the stage default to 65% (override).",
    );
  });
});
