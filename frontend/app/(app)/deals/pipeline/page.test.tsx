import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PipelinePage from "@/app/(app)/deals/pipeline/page";
import { ToastProvider } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { changeDealStage, getDeal, getDealHistory, listDeals } from "@/lib/api/deals";
import { getPipelineSummary } from "@/lib/api/pipeline";
import type { Deal, DealStage, PipelineSummary } from "@/types/api";

vi.mock("@/lib/api/deals", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/deals")>();
  return {
    ...actual,
    listDeals: vi.fn(),
    changeDealStage: vi.fn(),
    getDeal: vi.fn(),
    getDealHistory: vi.fn(),
  };
});
vi.mock("@/lib/api/pipeline", () => ({ getPipelineSummary: vi.fn() }));

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

const listMock = vi.mocked(listDeals);
const stageMock = vi.mocked(changeDealStage);

function deal(overrides: Partial<Deal> = {}): Deal {
  return {
    id: "deal-1",
    name: "Acme expansion",
    description: null,
    amount: "125000.50",
    currency: "INR",
    stage: "QUALIFICATION",
    probability: null,
    effective_probability: 10,
    probability_source: "STAGE_DEFAULT",
    forecast_category: "PIPELINE",
    expected_close_date: "2099-12-15",
    closed_at: null,
    owner_user_id: "user-1",
    owner_name: "Olivia Owner",
    lead_id: null,
    lead_name: null,
    lost_reason: null,
    revision: 2,
    stage_entered_at: "2026-10-01T00:00:00Z",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-02T00:00:00Z",
    ...overrides,
  };
}

const summary: PipelineSummary = {
  currency: "INR",
  generated_at: "2026-10-29T00:00:00Z",
  open: { count: 2, total_amount: "126000.50", weighted_amount: "12600.05" },
  won: { count: 0, total_amount: "0.00" },
  lost: { count: 0, total_amount: "0.00" },
  overdue_open: { count: 1, total_amount: "1000.00" },
  by_stage: [
    { stage: "QUALIFICATION", count: 1, total_amount: "125000.50", weighted_amount: "12500.05", default_probability: 10 },
    { stage: "DISCOVERY", count: 1, total_amount: "1000.00", weighted_amount: "250.00", default_probability: 25 },
    { stage: "PROPOSAL", count: 0, total_amount: "0.00", weighted_amount: "0.00", default_probability: 50 },
    { stage: "NEGOTIATION", count: 0, total_amount: "0.00", weighted_amount: "0.00", default_probability: 75 },
    { stage: "CLOSED_WON", count: 0, total_amount: "0.00", weighted_amount: "0.00", default_probability: 100 },
    { stage: "CLOSED_LOST", count: 0, total_amount: "0.00", weighted_amount: "0.00", default_probability: 0 },
  ],
  won_by_month: [{ month: "2026-10-01", count: 0, total_amount: "0.00" }],
  excluded_other_currency_count: 0,
};

function boardData(byStage: Partial<Record<DealStage, { items: Deal[]; total?: number }>>) {
  listMock.mockImplementation(async (params) => {
    const column = byStage[params?.stage as DealStage] ?? { items: [] };
    return { items: column.items, limit: 50, offset: 0, total: column.total ?? column.items.length };
  });
}

function renderPage() {
  return render(
    <ToastProvider>
      <PipelinePage />
    </ToastProvider>,
  );
}

function column(name: RegExp) {
  return screen.getByRole("region", { name });
}

describe("Pipeline board", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.role = "OWNER";
    vi.mocked(getPipelineSummary).mockResolvedValue(summary);
    vi.mocked(getDealHistory).mockResolvedValue({ items: [], limit: 50, offset: 0, total: 0 });
    boardData({
      QUALIFICATION: { items: [deal()] },
      DISCOVERY: {
        items: [deal({ id: "deal-2", name: "Late pilot", stage: "DISCOVERY", amount: "1000.00", expected_close_date: "2020-01-01" })],
      },
    });
  });

  it("shows a column per stage with counts, exact totals and cards", async () => {
    renderPage();
    const qualification = await screen.findByRole("region", { name: /^Qualification, 1 deal/ });
    expect(within(qualification).getByText("₹1,25,000.50")).toBeInTheDocument();
    expect(within(qualification).getByTitle("₹1,25,000.50")).toBeInTheDocument();
    expect(within(qualification).getByText("Olivia Owner")).toBeInTheDocument();
    for (const name of [/^Proposal, 0 deals/, /^Negotiation, 0 deals/, /^Closed won, 0 deals/, /^Closed lost, 0 deals/]) {
      expect(within(column(name)).getByText("No deals in this stage")).toBeInTheDocument();
    }
    expect(within(column(/^Discovery/)).getByText(/Overdue ·/)).toBeInTheDocument();
    expect(listMock).toHaveBeenCalledWith({ stage: "PROPOSAL", limit: 50 });
    expect(getPipelineSummary).toHaveBeenCalledWith(1);
  });

  it("shows the forecast category on open deal cards", async () => {
    boardData({
      QUALIFICATION: { items: [deal({ forecast_category: "COMMIT" })] },
      CLOSED_WON: {
        items: [deal({ id: "deal-won", name: "Won", stage: "CLOSED_WON", forecast_category: null })],
      },
    });
    renderPage();
    const qualification = await screen.findByRole("region", { name: /^Qualification, 1 deal/ });
    expect(within(qualification).getByText("Commit")).toBeInTheDocument();
    // The Closed won column already says the outcome; no badge repeats it.
    const won = screen.getByRole("region", { name: /^Closed won, 1 deal/ });
    expect(won.querySelector("[data-slot=forecast-category-badge]")).toBeNull();
  });

  it("shows Pipeline on a reopened card while the move is pending", async () => {
    const user = userEvent.setup();
    authMock.role = "MEMBER"; // lost deals reopen for every role
    boardData({
      CLOSED_LOST: {
        items: [
          deal({
            stage: "CLOSED_LOST",
            forecast_category: null,
            lost_reason: "Budget",
            closed_at: "2026-10-01T00:00:00Z",
          }),
        ],
      },
    });
    let resolve: (value: Deal) => void = () => {};
    stageMock.mockReturnValue(new Promise((done) => (resolve = done)));
    renderPage();
    await screen.findByRole("region", { name: /^Closed lost, 1 deal/ });
    await user.click(screen.getByRole("button", { name: "Move Acme expansion" }));
    await user.click(await screen.findByRole("menuitem", { name: "Qualification" }));
    const qualification = await screen.findByRole("region", { name: /^Qualification, 1 deal/ });
    const badge = qualification.querySelector("[data-slot=forecast-category-badge]");
    expect(badge).toHaveTextContent("Pipeline");
    expect(within(qualification).queryByText("—")).not.toBeInTheDocument();
    await act(async () => resolve(deal({ forecast_category: "PIPELINE", revision: 3 })));
  });

  it("shows the forecast category in the deal drawer", async () => {
    const user = userEvent.setup();
    boardData({ QUALIFICATION: { items: [deal({ forecast_category: "BEST_CASE" })] } });
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Acme expansion" }));
    const drawer = await screen.findByRole("dialog", { name: "Acme expansion" });
    const label = within(drawer).getByText("Forecast category", { selector: "dt" });
    expect(label.nextElementSibling).toHaveTextContent("Best case");
  });

  it("moves a deal to an open stage with its current revision", async () => {
    const user = userEvent.setup();
    stageMock.mockResolvedValue(deal({ stage: "PROPOSAL", revision: 3, effective_probability: 50 }));
    renderPage();
    await screen.findByRole("region", { name: /^Qualification/ });
    await user.click(screen.getByRole("button", { name: "Move Acme expansion" }));
    await user.click(await screen.findByRole("menuitem", { name: "Proposal" }));
    expect(stageMock).toHaveBeenCalledWith("deal-1", {
      stage: "PROPOSAL",
      expected_revision: 2,
      probability: null,
      lost_reason: null,
      change_reason: null,
    });
    expect(await within(column(/^Proposal/)).findByText("Acme expansion")).toBeInTheDocument();
    expect(within(column(/^Qualification/)).queryByText("Acme expansion")).not.toBeInTheDocument();
    expect(await screen.findByText("Moved to Proposal")).toBeInTheDocument();
  });

  it("reverts and reloads when the deal changed elsewhere", async () => {
    const user = userEvent.setup();
    stageMock.mockRejectedValue(new ApiError("Request failed: 409", 409, { current_revision: 3 }));
    renderPage();
    await screen.findByRole("region", { name: /^Qualification/ });
    const loads = listMock.mock.calls.length;
    await user.click(screen.getByRole("button", { name: "Move Acme expansion" }));
    await user.click(await screen.findByRole("menuitem", { name: "Negotiation" }));
    expect((await screen.findAllByText("This deal changed elsewhere")).length).toBeGreaterThan(0);
    await waitFor(() => expect(listMock.mock.calls.length).toBeGreaterThan(loads));
    expect(within(column(/^Qualification/)).getByText("Acme expansion")).toBeInTheDocument();
  });

  it("asks for confirmation before closing a deal", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("region", { name: /^Qualification/ });
    await user.click(screen.getByRole("button", { name: "Move Acme expansion" }));
    await user.click(await screen.findByRole("menuitem", { name: "Closed won" }));
    const dialog = await screen.findByRole("dialog", { name: "Change stage" });
    expect(within(dialog).getByLabelText(/New stage/)).toHaveValue("CLOSED_WON");
    expect(within(dialog).getByRole("button", { name: "Mark as won" })).toBeInTheDocument();
    expect(stageMock).not.toHaveBeenCalled();
  });

  it("moves a deal by drag and drop", async () => {
    stageMock.mockResolvedValue(deal({ stage: "DISCOVERY", revision: 3 }));
    renderPage();
    const card = (await screen.findByRole("button", { name: "Acme expansion" })).closest("li")!;
    const data = new Map<string, string>();
    const dataTransfer = {
      setData: (type: string, value: string) => data.set(type, value),
      getData: (type: string) => data.get(type) ?? "",
      get types() {
        return [...data.keys()];
      },
      effectAllowed: "",
    };
    fireEvent.dragStart(card, { dataTransfer });
    const target = column(/^Discovery/);
    fireEvent.dragOver(target, { dataTransfer });
    await act(async () => {
      fireEvent.drop(target, { dataTransfer });
    });
    expect(stageMock).toHaveBeenCalledWith("deal-1", expect.objectContaining({ stage: "DISCOVERY", expected_revision: 2 }));
  });

  it("opens a deal drawer with history and a link to the full page", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Acme expansion" }));
    const drawer = await screen.findByRole("dialog", { name: "Acme expansion" });
    expect(within(drawer).getByText(/₹1,25,000.50 · closes Dec 15, 2099/)).toBeInTheDocument();
    expect(within(drawer).getByRole("link", { name: /Open deal/ })).toHaveAttribute("href", "/deals/deal-1");
    expect(await within(drawer).findByText("No changes have been recorded yet.")).toBeInTheDocument();
    expect(getDealHistory).toHaveBeenCalledWith("deal-1", { limit: 50 });
  });

  it("links to the full list when a column has more deals than it shows", async () => {
    boardData({ QUALIFICATION: { items: [deal()], total: 75 } });
    renderPage();
    expect(await screen.findByRole("link", { name: "View all 75 in the list" })).toHaveAttribute(
      "href",
      "/deals?stage=QUALIFICATION",
    );
  });

  it("shows an error and retries", async () => {
    const user = userEvent.setup();
    listMock.mockRejectedValueOnce(new Error("network"));
    renderPage();
    expect(await screen.findByText("The pipeline could not be loaded")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("region", { name: /^Qualification/ })).toBeInTheDocument();
    expect(vi.mocked(getDeal)).not.toHaveBeenCalled();
  });

  describe("won deals by role", () => {
    const won = deal({
      id: "deal-won",
      name: "Signed renewal",
      stage: "CLOSED_WON",
      effective_probability: 100,
      closed_at: "2026-10-20T00:00:00Z",
    });

    function transfer() {
      const data = new Map<string, string>();
      return {
        setData: (type: string, value: string) => data.set(type, value),
        getData: (type: string) => data.get(type) ?? "",
        get types() {
          return [...data.keys()];
        },
        effectAllowed: "",
      };
    }

    beforeEach(() => {
      boardData({ QUALIFICATION: { items: [deal()] }, CLOSED_WON: { items: [won] } });
    });

    it.each(["OWNER", "ADMIN"])("lets %s move a won deal", async (role) => {
      const user = userEvent.setup();
      authMock.role = role;
      stageMock.mockResolvedValue({ ...won, stage: "NEGOTIATION", closed_at: null, revision: 3 });
      renderPage();
      await screen.findByRole("region", { name: /^Closed won/ });
      const card = screen.getByRole("button", { name: "Signed renewal" }).closest("li")!;
      expect(card).toHaveAttribute("draggable", "true");
      expect(screen.queryByText(/Only owners and admins can move won deals/)).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Move Signed renewal" }));
      await user.click(await screen.findByRole("menuitem", { name: "Negotiation" }));
      expect(stageMock).toHaveBeenCalledWith("deal-won", expect.objectContaining({ stage: "NEGOTIATION" }));
    });

    it("gives members no way to move a won deal, by menu or drag and drop", async () => {
      authMock.role = "MEMBER";
      renderPage();
      await screen.findByRole("region", { name: /^Closed won/ });
      expect(screen.getByText(/Only owners and admins can move won deals/)).toBeInTheDocument();
      const card = screen.getByRole("button", { name: "Signed renewal" }).closest("li")!;
      expect(card).toHaveAttribute("draggable", "false");
      expect(screen.queryByRole("button", { name: "Move Signed renewal" })).not.toBeInTheDocument();
      expect(
        within(card).getByRole("img", { name: "Only owners and admins can reopen or change a won deal." }),
      ).toBeInTheDocument();

      // Even a forged drop (e.g. dragged in from elsewhere) never reaches the API.
      const dataTransfer = transfer();
      dataTransfer.setData("application/x-flowpilot-deal", "deal-won");
      const target = column(/^Proposal/);
      fireEvent.dragOver(target, { dataTransfer });
      await act(async () => {
        fireEvent.drop(target, { dataTransfer });
      });
      expect(stageMock).not.toHaveBeenCalled();
      expect((await screen.findAllByText("This deal cannot be moved")).length).toBeGreaterThan(0);
      expect(within(column(/^Closed won/)).getByText("Signed renewal")).toBeInTheDocument();
    });

    it("still lets members move open deals, including closing them", async () => {
      const user = userEvent.setup();
      authMock.role = "MEMBER";
      stageMock.mockResolvedValue(deal({ stage: "DISCOVERY", revision: 3 }));
      renderPage();
      await screen.findByRole("region", { name: /^Qualification/ });
      const card = screen.getByRole("button", { name: "Acme expansion" }).closest("li")!;
      expect(card).toHaveAttribute("draggable", "true");
      await user.click(screen.getByRole("button", { name: "Move Acme expansion" }));
      await user.click(await screen.findByRole("menuitem", { name: "Closed won" }));
      const dialog = await screen.findByRole("dialog", { name: "Change stage" });
      expect(within(dialog).getByRole("button", { name: "Mark as won" })).toBeInTheDocument();
      expect(within(dialog).getByRole("note")).toHaveTextContent(
        "Only owners and admins can reopen or change a won deal",
      );
    });

    it("shows the API's reason when it refuses a move", async () => {
      const user = userEvent.setup();
      stageMock.mockRejectedValue(
        new ApiError("Request failed: 403", 403, {
          detail: "Only owners and admins can move a won deal to another stage",
        }),
      );
      renderPage();
      await screen.findByRole("region", { name: /^Closed won/ });
      await user.click(screen.getByRole("button", { name: "Move Signed renewal" }));
      await user.click(await screen.findByRole("menuitem", { name: "Proposal" }));
      expect(
        (await screen.findAllByText("Only owners and admins can move a won deal to another stage"))
          .length,
      ).toBeGreaterThan(0);
      expect(within(column(/^Closed won/)).getByText("Signed renewal")).toBeInTheDocument();
    });
  });
});
