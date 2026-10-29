import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DealsPage from "@/app/(app)/deals/page";
import { ToastProvider } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { createDeal, listDeals } from "@/lib/api/deals";
import { getLead, getLeads } from "@/lib/api/leads";
import { getCurrentOrganization, listOrganizationMembers } from "@/lib/api/organizations";
import type { Deal, DealListResponse, MemberPublic } from "@/types/api";

const mockReplace = vi.fn();
let currentSearch = "";
const listeners = new Set<() => void>();
const authMock = vi.hoisted(() => ({ role: "OWNER" as string, userId: "user-owner" }));

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
    usePathname: () => "/deals",
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

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    session: {
      user: { id: authMock.userId, name: "Olivia Owner", email: "o@example.com" },
      organization: { id: "org-1", name: "Acme", slug: "acme" },
      membership: { role: authMock.role },
    },
    isLoading: false,
  }),
}));

vi.mock("@/lib/api/deals", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/deals")>();
  return { ...actual, listDeals: vi.fn(), createDeal: vi.fn() };
});
vi.mock("@/lib/api/leads", () => ({ getLeads: vi.fn(), getLead: vi.fn() }));
vi.mock("@/lib/api/organizations", () => ({
  getCurrentOrganization: vi.fn(),
  listOrganizationMembers: vi.fn(),
}));

const listMock = vi.mocked(listDeals);
const createMock = vi.mocked(createDeal);
const getLeadsMock = vi.mocked(getLeads);
const getLeadMock = vi.mocked(getLead);

const members: MemberPublic[] = [
  { membership_id: "m-1", role: "OWNER", user: { id: "user-owner", name: "Olivia Owner", email: "o@example.com" } },
  { membership_id: "m-2", role: "MEMBER", user: { id: "user-member", name: "Max Member", email: "m@example.com" } },
];

function deal(overrides: Partial<Deal> = {}): Deal {
  return {
    id: "deal-1",
    name: "Acme expansion",
    description: null,
    amount: "125000.50",
    currency: "INR",
    stage: "PROPOSAL",
    probability: null,
    effective_probability: 50,
    probability_source: "STAGE_DEFAULT",
    expected_close_date: "2026-12-15",
    closed_at: null,
    owner_user_id: "user-owner",
    owner_name: "Olivia Owner",
    lead_id: "lead-1",
    lead_name: "Ada Prospect",
    lost_reason: null,
    revision: 1,
    stage_entered_at: "2026-10-01T10:00:00Z",
    created_at: "2026-10-01T10:00:00Z",
    updated_at: "2026-10-28T10:00:00Z",
    ...overrides,
  };
}

function pageOf(items: Deal[], total = items.length, offset = 0): DealListResponse {
  return { items, limit: 20, offset, total };
}

function renderPage() {
  return render(
    <ToastProvider>
      <DealsPage />
    </ToastProvider>,
  );
}

function lastListParams() {
  return listMock.mock.calls.at(-1)?.[0];
}

describe("Deals page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentSearch = "";
    listeners.clear();
    authMock.role = "OWNER";
    listMock.mockResolvedValue(pageOf([deal()]));
    vi.mocked(getCurrentOrganization).mockResolvedValue({
      id: "org-1",
      name: "Acme",
      slug: "acme",
      default_currency: "INR",
    });
    vi.mocked(listOrganizationMembers).mockResolvedValue(members);
    getLeadsMock.mockResolvedValue({
      items: [],
      limit: 8,
      offset: 0,
      total: 0,
      status_counts: { NEW: 0, CONTACTED: 0, QUALIFIED: 0, UNQUALIFIED: 0, CONVERTED: 0 },
    });
  });

  it("shows loading, then deals with formatted money, links and probability", async () => {
    renderPage();
    expect(screen.getByText("Loading records")).toBeInTheDocument();
    const links = await screen.findAllByRole("link", { name: "Acme expansion" });
    expect(links[0]).toHaveAttribute("href", "/deals/deal-1");
    expect(screen.getAllByRole("link", { name: "Ada Prospect" })[0]).toHaveAttribute(
      "href",
      "/leads/lead-1",
    );
    expect(screen.getAllByText("₹1,25,000.50").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Proposal").length).toBeGreaterThan(0);
    expect(screen.getAllByText("50%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("stage default").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Dec 15, 2026").length).toBeGreaterThan(0);
    expect(screen.getByText("1 deal in your pipeline.")).toBeInTheDocument();
    expect(screen.getByText("Showing 1–1 of 1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sales targets" })).toHaveAttribute(
      "href",
      "/deals/targets",
    );
  });

  it("debounces search into the URL and the API query", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findAllByRole("link", { name: "Acme expansion" });
    await user.type(screen.getByRole("searchbox", { name: "Search deals" }), "acme");
    await waitFor(() =>
      expect(mockReplace).toHaveBeenLastCalledWith("/deals?q=acme", { scroll: false }),
    );
    await waitFor(() => expect(lastListParams()).toMatchObject({ q: "acme", offset: 0 }));
  });

  it("filters by stage, owner and close date and resets paging", async () => {
    const user = userEvent.setup();
    currentSearch = "offset=20";
    listMock.mockResolvedValue(pageOf([deal()], 21, 20));
    renderPage();
    await screen.findByText("Showing 21–21 of 21");
    await user.selectOptions(screen.getByRole("combobox", { name: "Stage" }), "NEGOTIATION");
    expect(mockReplace).toHaveBeenLastCalledWith("/deals?stage=NEGOTIATION", { scroll: false });
    await screen.findByRole("option", { name: "Max Member" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Owner" }), "user-member");
    expect(mockReplace).toHaveBeenLastCalledWith(
      "/deals?stage=NEGOTIATION&owner=user-member",
      { scroll: false },
    );
    await waitFor(() =>
      expect(lastListParams()).toMatchObject({
        stage: "NEGOTIATION",
        ownerUserId: "user-member",
        offset: 0,
      }),
    );
  });

  it("validates the close-date range without calling the API", async () => {
    currentSearch = "from=2026-12-31&to=2026-01-01";
    renderPage();
    expect(
      await screen.findByText("The start of the close-date range must be on or before the end."),
    ).toBeInTheDocument();
    expect(listMock).not.toHaveBeenCalled();
  });

  it("paginates with Previous and Next", async () => {
    const user = userEvent.setup();
    listMock.mockImplementation(async (params) =>
      pageOf([deal({ id: `deal-${params?.offset ?? 0}` })], 45, params?.offset ?? 0),
    );
    renderPage();
    await screen.findByText("Showing 1–20 of 45");
    expect(screen.getByRole("button", { name: "Previous deals page" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next deals page" }));
    expect(mockReplace).toHaveBeenLastCalledWith("/deals?offset=20", { scroll: false });
    await screen.findByText("Showing 21–40 of 45");
  });

  it("shows empty, filtered-empty and error states with recovery", async () => {
    const user = userEvent.setup();
    listMock.mockResolvedValueOnce(pageOf([]));
    const { unmount } = renderPage();
    expect(await screen.findByRole("heading", { name: "No deals yet" })).toBeInTheDocument();
    unmount();

    currentSearch = "stage=CLOSED_LOST";
    listMock.mockResolvedValueOnce(pageOf([]));
    const filtered = renderPage();
    expect(
      await screen.findByRole("heading", { level: 3, name: "No deals match these filters" }),
    ).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Clear filters" }).at(-1)!);
    expect(mockReplace).toHaveBeenLastCalledWith("/deals", { scroll: false });
    filtered.unmount();

    currentSearch = "";
    listMock.mockRejectedValueOnce(new Error("network"));
    renderPage();
    expect(
      await screen.findByRole("heading", { level: 3, name: "Deals could not be loaded" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect((await screen.findAllByRole("link", { name: "Acme expansion" })).length).toBeGreaterThan(0);
  });

  describe("creating a deal", () => {
    async function openForm(user: ReturnType<typeof userEvent.setup>) {
      renderPage();
      await screen.findAllByRole("link", { name: "Acme expansion" });
      await user.click(screen.getByRole("button", { name: "Create deal" }));
      return screen.findByRole("dialog", { name: "Create deal" });
    }

    it("validates fields before sending anything", async () => {
      const user = userEvent.setup();
      const dialog = await openForm(user);
      expect(within(dialog).getByLabelText(/Currency/)).toHaveValue("INR");
      expect(within(dialog).getByLabelText(/Probability override/)).toHaveAccessibleDescription(
        "Leave blank to use the stage default.",
      );
      await user.type(within(dialog).getByLabelText(/Amount/), "12.345");
      await user.selectOptions(within(dialog).getByLabelText("Stage"), "CLOSED_LOST");
      await user.click(within(dialog).getByRole("button", { name: "Create deal" }));
      expect(within(dialog).getByText("Enter a deal name.")).toBeInTheDocument();
      expect(within(dialog).getByText("Use at most 2 decimal places.")).toBeInTheDocument();
      expect(within(dialog).getByText("Choose an expected close date.")).toBeInTheDocument();
      expect(within(dialog).getByText("Explain why the deal was lost.")).toBeInTheDocument();
      expect(within(dialog).getByLabelText(/Probability override/)).toBeDisabled();
      expect(createMock).not.toHaveBeenCalled();
    });

    it("sends exact string amounts once, then confirms and refreshes", async () => {
      const user = userEvent.setup();
      let resolve: (value: Deal) => void = () => {};
      createMock.mockReturnValue(new Promise((done) => (resolve = done)));
      const dialog = await openForm(user);
      await user.type(within(dialog).getByLabelText(/Deal name/), "  New pilot  ");
      await user.type(within(dialog).getByLabelText(/Amount/), "1,25,000.5");
      await user.type(within(dialog).getByLabelText(/Probability override/), "35");
      await user.type(within(dialog).getByLabelText(/Expected close date/), "2027-01-31");
      const submit = within(dialog).getByRole("button", { name: "Create deal" });
      await user.click(submit);
      await user.click(within(dialog).getByRole("button", { name: "Saving…" }));
      expect(createMock).toHaveBeenCalledTimes(1);
      expect(createMock).toHaveBeenCalledWith({
        name: "New pilot",
        description: null,
        amount: "125000.5",
        stage: "QUALIFICATION",
        probability: 35,
        expected_close_date: "2027-01-31",
        lead_id: null,
      });
      const calls = listMock.mock.calls.length;
      await act(async () => resolve(deal({ id: "deal-new", name: "New pilot", lead_name: null })));
      expect(await screen.findByText("Deal created")).toBeInTheDocument();
      await waitFor(() => expect(listMock.mock.calls.length).toBeGreaterThan(calls));
      expect(mockReplace).toHaveBeenLastCalledWith("/deals", { scroll: false });
    });

    it("maps server validation and permission errors onto fields", async () => {
      const user = userEvent.setup();
      createMock.mockRejectedValueOnce(
        new ApiError("Request failed: 422", 422, {
          detail: [{ loc: ["body", "expected_close_date"], msg: "Input should be a valid date" }],
        }),
      );
      const dialog = await openForm(user);
      await user.type(within(dialog).getByLabelText(/Deal name/), "Deal");
      await user.type(within(dialog).getByLabelText(/Amount/), "10");
      await user.type(within(dialog).getByLabelText(/Expected close date/), "2027-01-31");
      await user.click(within(dialog).getByRole("button", { name: "Create deal" }));
      expect(await within(dialog).findByText("Input should be a valid date")).toBeInTheDocument();
      expect(within(dialog).getByLabelText(/Expected close date/)).toHaveAttribute(
        "aria-invalid",
        "true",
      );

      createMock.mockRejectedValueOnce(new ApiError("Request failed: 404", 404));
      await user.click(within(dialog).getByRole("button", { name: "Create deal" }));
      expect(
        await within(dialog).findByText(
          "This lead no longer exists or is not in your organization.",
        ),
      ).toBeInTheDocument();
    });

    it("lets owners and admins assign other members, but not members", async () => {
      const user = userEvent.setup();
      let dialog = await openForm(user);
      const ownerOptions = within(within(dialog).getByLabelText("Owner"))
        .getAllByRole("option")
        .map((option) => option.textContent);
      expect(ownerOptions).toEqual(["Me", "Unassigned", "Max Member"]);
      cleanup();

      authMock.role = "MEMBER";
      currentSearch = "";
      dialog = await openForm(user);
      const memberOptions = within(within(dialog).getByLabelText("Owner"))
        .getAllByRole("option")
        .map((option) => option.textContent);
      expect(memberOptions).toEqual(["Me", "Unassigned"]);
    });

    it("searches for and links a lead", async () => {
      const user = userEvent.setup();
      getLeadsMock.mockResolvedValue({
        items: [
          {
            id: "lead-9",
            name: "Grace Lead",
            email: "grace@example.com",
            phone: null,
            company: null,
            source: "MANUAL",
            status: "QUALIFIED",
            notes: null,
            created_at: "2026-10-01T00:00:00Z",
            updated_at: "2026-10-01T00:00:00Z",
          },
        ] as never,
        limit: 8,
        offset: 0,
        total: 1,
        status_counts: { NEW: 0, CONTACTED: 0, QUALIFIED: 1, UNQUALIFIED: 0, CONVERTED: 0 },
      });
      createMock.mockResolvedValue(deal({ id: "deal-2", lead_name: "Grace Lead" }));
      const dialog = await openForm(user);
      await user.type(within(dialog).getByLabelText(/Associated lead/), "gra");
      await user.click(await within(dialog).findByRole("button", { name: /Grace Lead/ }));
      expect(getLeadsMock).toHaveBeenCalledWith({ q: "gra", limit: 8 });
      await user.type(within(dialog).getByLabelText(/Deal name/), "Grace deal");
      await user.type(within(dialog).getByLabelText(/Amount/), "500");
      await user.type(within(dialog).getByLabelText(/Expected close date/), "2027-02-01");
      await user.click(within(dialog).getByRole("button", { name: "Create deal" }));
      expect(createMock).toHaveBeenCalledWith(expect.objectContaining({ lead_id: "lead-9" }));
      expect(await screen.findByText(/Grace Lead is now converted/)).toBeInTheDocument();
    });

    it("opens prefilled from a lead link", async () => {
      currentSearch = "create=1&lead_id=lead-7";
      getLeadMock.mockResolvedValue({ id: "lead-7", name: "Linked Lead" } as never);
      renderPage();
      const dialog = await screen.findByRole("dialog", { name: "Create deal" });
      expect(within(dialog).getByText("Linked Lead")).toBeInTheDocument();
      expect(getLeadMock).toHaveBeenCalledWith("lead-7");
    });

    it("still opens the form when a linked lead cannot be loaded", async () => {
      currentSearch = "create=1&lead_id=lead-gone";
      getLeadMock.mockRejectedValue(new ApiError("Request failed: 404", 404));
      renderPage();
      const dialog = await screen.findByRole("dialog", { name: "Create deal" });
      expect(within(dialog).getByLabelText(/Associated lead/)).toHaveValue("");
      // Error toasts also render a live-region copy for screen readers.
      expect((await screen.findAllByText("Lead not available")).length).toBeGreaterThan(0);
      // The failed lookup is not retried in a loop.
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(getLeadMock).toHaveBeenCalledTimes(1);
    });
  });
});
