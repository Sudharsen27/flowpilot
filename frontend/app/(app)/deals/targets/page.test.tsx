import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTargetsPage from "@/app/(app)/deals/targets/page";
import { ToastProvider } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/client";
import { getCurrentOrganization, listOrganizationMembers } from "@/lib/api/organizations";
import { listSalesTargets, upsertSalesTarget } from "@/lib/api/sales-targets";
import type { MemberPublic, SalesTarget } from "@/types/api";

const authMock = vi.hoisted(() => ({ role: "OWNER" as string }));

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
vi.mock("@/lib/api/sales-targets", () => ({
  listSalesTargets: vi.fn(),
  upsertSalesTarget: vi.fn(),
}));
vi.mock("@/lib/api/organizations", () => ({
  getCurrentOrganization: vi.fn(),
  listOrganizationMembers: vi.fn(),
}));

const listMock = vi.mocked(listSalesTargets);
const upsertMock = vi.mocked(upsertSalesTarget);
const YEAR = new Date().getFullYear();

const members: MemberPublic[] = [
  { membership_id: "m-1", role: "OWNER", user: { id: "user-owner", name: "Olivia Owner", email: "o@example.com" } },
  { membership_id: "m-2", role: "MEMBER", user: { id: "user-member", name: "Max Member", email: "m@example.com" } },
];

function target(overrides: Partial<SalesTarget> = {}): SalesTarget {
  return {
    id: "t-1",
    owner_user_id: null,
    owner_name: null,
    period_start: `${YEAR}-11-01`,
    period_end: `${YEAR}-11-30`,
    amount: "500000.00",
    currency: "INR",
    created_by_user_id: "user-owner",
    updated_by_user_id: "user-owner",
    created_at: `${YEAR}-01-01T00:00:00Z`,
    updated_at: `${YEAR}-01-02T00:00:00Z`,
    ...overrides,
  };
}

function renderPage() {
  return render(
    <ToastProvider>
      <SalesTargetsPage />
    </ToastProvider>,
  );
}

describe("Sales targets page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.role = "OWNER";
    listMock.mockResolvedValue({
      items: [
        target(),
        target({ id: "t-2", owner_user_id: "user-member", owner_name: "Max Member", amount: "125000.5" }),
      ],
      limit: 200,
      offset: 0,
      total: 2,
    });
    vi.mocked(getCurrentOrganization).mockResolvedValue({
      id: "org-1",
      name: "Acme",
      slug: "acme",
      default_currency: "INR",
    });
    vi.mocked(listOrganizationMembers).mockResolvedValue(members);
  });

  it("shows a month grid of organization targets and owner targets for the year", async () => {
    renderPage();
    expect(await screen.findAllByText(`November ${YEAR}`)).not.toHaveLength(0);
    expect(listMock).toHaveBeenCalledWith({
      periodFrom: `${YEAR}-01-01`,
      periodTo: `${YEAR}-12-01`,
      limit: 200,
    });
    expect(screen.getAllByText("₹5,00,000.00").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Not set").length).toBeGreaterThan(0);
    const ownerSection = screen.getByRole("region", { name: "Owner targets" });
    expect(within(ownerSection).getAllByText("Max Member").length).toBeGreaterThan(0);
    expect(within(ownerSection).getAllByText("₹1,25,000.50").length).toBeGreaterThan(0);
    expect(await screen.findByText(/Monthly revenue targets in INR/)).toBeInTheDocument();
  });

  it("creates an organization-wide target with an exact string amount", async () => {
    const user = userEvent.setup();
    upsertMock.mockResolvedValue(target({ id: "t-3", period_start: `${YEAR}-03-01`, amount: "750000.00" }));
    renderPage();
    // DataTable renders desktop and mobile layouts, so each row action appears twice.
    await user.click((await screen.findAllByRole("button", { name: `Set target for March ${YEAR}` }))[0]!);
    const dialog = await screen.findByRole("dialog", { name: "Set sales target" });
    expect(within(dialog).getByLabelText("Month")).toBeDisabled();
    expect(within(dialog).getByLabelText(/Currency/)).toHaveValue("INR");
    await user.type(within(dialog).getByLabelText(/Target amount/), "7,50,000");
    await user.click(within(dialog).getByRole("button", { name: "Set target" }));
    expect(upsertMock).toHaveBeenCalledWith({ period_start: `${YEAR}-03-01`, amount: "750000" });
    expect(await screen.findByText("Target set")).toBeInTheDocument();
    await waitFor(() => expect(listMock).toHaveBeenCalledTimes(2));
  });

  it("updates an existing target and says it will be replaced", async () => {
    const user = userEvent.setup();
    upsertMock.mockResolvedValue(target({ amount: "600000.00" }));
    renderPage();
    await user.click(
      (await screen.findAllByRole("button", { name: `Edit target for November ${YEAR}` }))[0]!,
    );
    const dialog = await screen.findByRole("dialog", { name: "Update sales target" });
    expect(within(dialog).getByText(/Current target: ₹5,00,000.00\. Saving replaces it\./)).toBeInTheDocument();
    const amount = within(dialog).getByLabelText(/Target amount/);
    expect(amount).toHaveValue("500000.00");
    await user.clear(amount);
    await user.type(amount, "600000");
    await user.click(within(dialog).getByRole("button", { name: "Update target" }));
    expect(upsertMock).toHaveBeenCalledWith({ period_start: `${YEAR}-11-01`, amount: "600000" });
    expect(await screen.findByText("Target updated")).toBeInTheDocument();
  });

  it("sets an owner target from the general dialog", async () => {
    const user = userEvent.setup();
    upsertMock.mockResolvedValue(target({ id: "t-9", owner_user_id: "user-owner", owner_name: "Olivia Owner" }));
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Set target" }));
    const dialog = await screen.findByRole("dialog", { name: "Set sales target" });
    await screen.findByRole("option", { name: "Olivia Owner" });
    await user.selectOptions(within(dialog).getByLabelText("Month"), `${YEAR}-05-01`);
    await user.selectOptions(within(dialog).getByLabelText("Applies to"), "user-owner");
    await user.type(within(dialog).getByLabelText(/Target amount/), "100");
    await user.click(within(dialog).getByRole("button", { name: "Set target" }));
    expect(upsertMock).toHaveBeenCalledWith({
      period_start: `${YEAR}-05-01`,
      amount: "100",
      owner_user_id: "user-owner",
    });
  });

  it("validates amounts and reports permission errors", async () => {
    const user = userEvent.setup();
    upsertMock.mockRejectedValueOnce(new ApiError("Request failed: 403", 403));
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Set target" }));
    const dialog = await screen.findByRole("dialog", { name: "Set sales target" });
    await user.type(within(dialog).getByLabelText(/Target amount/), "-1");
    await user.click(within(dialog).getByRole("button", { name: "Set target" }));
    expect(within(dialog).getByText("Amount cannot be negative.")).toBeInTheDocument();
    expect(upsertMock).not.toHaveBeenCalled();
    await user.clear(within(dialog).getByLabelText(/Target amount/));
    await user.type(within(dialog).getByLabelText(/Target amount/), "10");
    await user.click(within(dialog).getByRole("button", { name: "Set target" }));
    expect(
      await within(dialog).findByText("Only owners and admins can set sales targets."),
    ).toBeInTheDocument();
  });

  it("gives members a read-only view", async () => {
    authMock.role = "MEMBER";
    renderPage();
    expect(await screen.findAllByText("₹5,00,000.00")).not.toHaveLength(0);
    expect(
      screen.getByText("You can view targets. Only owners and admins can set or change them."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Set target" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Edit target/ })).not.toBeInTheDocument();
  });

  it("moves between years and recovers from errors", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findAllByText(`November ${YEAR}`);
    listMock.mockRejectedValueOnce(new Error("network"));
    await user.click(screen.getByRole("button", { name: "Next year" }));
    expect(await screen.findByText("Sales targets could not be loaded")).toBeInTheDocument();
    expect(listMock).toHaveBeenLastCalledWith({
      periodFrom: `${YEAR + 1}-01-01`,
      periodTo: `${YEAR + 1}-12-01`,
      limit: 200,
    });
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findAllByText(`November ${YEAR + 1}`)).not.toHaveLength(0);
  });
});
