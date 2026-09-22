import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ApprovalsPage from "@/app/(app)/approvals/page";
import { getApprovals } from "@/lib/api/approvals";
import { ApiError } from "@/lib/api/client";
import {
  approveLeadResponseDraft,
  getLead,
  getLeadQualification,
  rejectLeadResponseDraft,
  sendLeadResponseDraft,
  updateLeadResponseDraft,
} from "@/lib/api/leads";
import { getSalesRun, sendSalesRun } from "@/lib/api/sales-runs";
import type { ApprovalListResponse, ApprovalQueueItem } from "@/types/api";

const mockReplace = vi.fn();
let currentSearch = "";
const searchListeners = new Set<() => void>();

function notifySearchListeners() {
  searchListeners.forEach((listener) => listener());
}

vi.mock("next/navigation", async () => {
  const React = await import("react");
  return {
    useRouter: () => ({
      replace: (href: string, options?: { scroll?: boolean }) => {
        mockReplace(href, options);
        currentSearch = href.includes("?") ? (href.split("?")[1] ?? "") : "";
        notifySearchListeners();
      },
      push: vi.fn(),
    }),
    usePathname: () => "/approvals",
    useSearchParams: () => {
      React.useSyncExternalStore(
        (onStoreChange) => {
          searchListeners.add(onStoreChange);
          return () => {
            searchListeners.delete(onStoreChange);
          };
        },
        () => currentSearch,
        () => currentSearch,
      );
      return new URLSearchParams(currentSearch);
    },
  };
});

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    className,
  }: {
    href: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/api/approvals", () => ({
  getApprovals: vi.fn(),
}));

vi.mock("@/lib/api/leads", () => ({
  getLead: vi.fn(),
  getLeadQualification: vi.fn(),
  approveLeadResponseDraft: vi.fn(),
  rejectLeadResponseDraft: vi.fn(),
  updateLeadResponseDraft: vi.fn(),
  sendLeadResponseDraft: vi.fn(),
}));

vi.mock("@/lib/api/sales-runs", () => ({
  getSalesRun: vi.fn(),
  sendSalesRun: vi.fn(),
}));

const getApprovalsMock = vi.mocked(getApprovals);
const getLeadMock = vi.mocked(getLead);
const getLeadQualificationMock = vi.mocked(getLeadQualification);
const approveMock = vi.mocked(approveLeadResponseDraft);
const rejectMock = vi.mocked(rejectLeadResponseDraft);
const updateMock = vi.mocked(updateLeadResponseDraft);
const sendDraftMock = vi.mocked(sendLeadResponseDraft);
const getSalesRunMock = vi.mocked(getSalesRun);
const sendSalesRunMock = vi.mocked(sendSalesRun);

function approvalItem(
  overrides: Partial<ApprovalQueueItem> = {},
): ApprovalQueueItem {
  return {
    draft_id: "draft-1",
    lead_id: "lead-1",
    lead: {
      name: "Jordan Lee",
      email: "jordan@acme.com",
      company: "Acme Technologies",
      status: "NEW",
      source: "WEBSITE",
    },
    enquiry: "We need a demo of FlowPilot next week.",
    draft: {
      response: "Thanks for reaching out about a demo. Happy to help.",
      review_status: "GENERATED",
      revision: 1,
      created_at: "2026-09-22T10:00:00Z",
      updated_at: "2026-09-22T10:05:00Z",
    },
    sales_run: {
      id: "run-1",
      status: "WAITING_APPROVAL",
      stage: "AWAIT_APPROVAL",
      agent_id: "agent-1",
      agent_name: "Sales Groq Verify",
    },
    email: null,
    needs_approval: true,
    can_approve: true,
    can_reject: true,
    can_edit: true,
    can_send: false,
    created_at: "2026-09-22T10:00:00Z",
    updated_at: "2026-09-22T10:05:00Z",
    ...overrides,
  };
}

function pageOf(items: ApprovalQueueItem[]): ApprovalListResponse {
  return { items, limit: 20, offset: 0, total: items.length };
}

describe("Approvals page", () => {
  beforeEach(() => {
    currentSearch = "";
    mockReplace.mockReset();
    getApprovalsMock.mockReset();
    getLeadMock.mockReset();
    getLeadQualificationMock.mockReset();
    approveMock.mockReset();
    rejectMock.mockReset();
    updateMock.mockReset();
    sendDraftMock.mockReset();
    getSalesRunMock.mockReset();
    sendSalesRunMock.mockReset();
    getApprovalsMock.mockResolvedValue(pageOf([]));
    getLeadMock.mockResolvedValue({
      id: "lead-1",
      name: "Jordan Lee",
      email: "jordan@acme.com",
      phone: null,
      company: "Acme Technologies",
      source: "WEBSITE",
      status: "NEW",
      notes: null,
      created_at: "2026-09-22T09:00:00Z",
      updated_at: "2026-09-22T10:00:00Z",
      latest_qualification: null,
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-09-22T12:00:00Z"));
  });

  afterEach(() => {
    searchListeners.clear();
    vi.useRealTimers();
  });

  it("selects the pending approval from the approval URL param", async () => {
    currentSearch = "approval=draft-1";
    const item = approvalItem();
    getApprovalsMock.mockResolvedValue(pageOf([item]));

    render(<ApprovalsPage />);

    await waitFor(() =>
      expect(getApprovalsMock).toHaveBeenCalledWith(
        expect.objectContaining({ status: "pending", limit: 20, offset: 0 }),
      ),
    );

    const detail = document.querySelector(
      "#approval-detail-pane",
    ) as HTMLElement;
    expect(
      await within(detail).findByRole("heading", { name: "Customer enquiry" }),
    ).toBeVisible();
    expect(
      within(detail).getByText("We need a demo of FlowPilot next week."),
    ).toBeVisible();
    expect(
      within(detail).getByRole("heading", { name: "AI-generated response" }),
    ).toBeVisible();
    expect(
      within(detail).getByText("This response has NOT been sent yet."),
    ).toBeVisible();
  });

  it("loads real API data into the queue and detail", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const item = approvalItem();
    getApprovalsMock.mockResolvedValue(pageOf([item]));

    render(<ApprovalsPage />);

    expect(
      await screen.findByRole("heading", { level: 1, name: "Approvals" }),
    ).toBeVisible();
    await waitFor(() =>
      expect(getApprovalsMock).toHaveBeenCalledWith(
        expect.objectContaining({ status: "pending", limit: 20, offset: 0 }),
      ),
    );

    expect(screen.getByText("Jordan Lee")).toBeVisible();
    expect(screen.getByText("Acme Technologies")).toBeVisible();
    expect(screen.getByText("jordan@acme.com")).toBeVisible();
    expect(
      screen.getByText(/Thanks for reaching out about a demo/),
    ).toBeVisible();
    expect(screen.getByText(/Sales Groq Verify/)).toBeVisible();
    expect(screen.getAllByText("Needs your review").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: /Jordan Lee/ }));

    const detail = document.querySelector(
      "#approval-detail-pane",
    ) as HTMLElement;
    expect(
      await within(detail).findByRole("heading", { name: "Customer enquiry" }),
    ).toBeVisible();
    expect(
      within(detail).getByText("We need a demo of FlowPilot next week."),
    ).toBeVisible();
    expect(
      within(detail).getByRole("heading", { name: "AI-generated response" }),
    ).toBeVisible();
    expect(
      within(detail).getByText("This response has NOT been sent yet."),
    ).toBeVisible();
    expect(within(detail).getByText("Sales Groq Verify")).toBeVisible();
    expect(
      within(detail).getByRole("link", { name: /Open Customer 360/ }),
    ).toHaveAttribute("href", "/leads/lead-1");
    expect(
      within(detail).queryByRole("button", { name: /Send/ }),
    ).not.toBeInTheDocument();
    expect(within(detail).getByRole("button", { name: "Edit" })).toBeEnabled();
    expect(within(detail).getByRole("button", { name: "Reject" })).toBeEnabled();
    expect(
      within(detail).getByRole("button", { name: "Approve" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("heading", { name: "Human decision required" }),
    ).toBeVisible();
  });

  it("shows empty pending state", async () => {
    render(<ApprovalsPage />);
    expect(
      await screen.findByRole("heading", { name: "You're all caught up." }),
    ).toBeVisible();
    expect(
      screen.getByText(/No responses are waiting for your review/i),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "View approved" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Open Inbox" })).toHaveAttribute(
      "href",
      "/inbox",
    );
  });

  it("shows error state with retry", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    getApprovalsMock.mockRejectedValueOnce(new Error("network"));
    getApprovalsMock.mockResolvedValue(pageOf([approvalItem()]));

    render(<ApprovalsPage />);

    expect(
      await screen.findByRole("heading", { name: "Couldn't load approvals." }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Acme Technologies")).toBeVisible();
  });

  it("approves without sending email and refreshes queue", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const item = approvalItem();
    getApprovalsMock
      .mockResolvedValueOnce(pageOf([item]))
      .mockResolvedValue(
        pageOf([
          approvalItem({
            draft: {
              ...item.draft,
              review_status: "APPROVED",
              revision: 2,
            },
            needs_approval: false,
            can_approve: false,
            can_send: true,
          }),
        ]),
      );
    approveMock.mockResolvedValue({
      id: "draft-1",
      lead_id: "lead-1",
      status: "COMPLETED",
      enquiry: item.enquiry,
      response: item.draft.response,
      review_status: "APPROVED",
      revision: 2,
      error: null,
      failure_category: null,
      provider: null,
      model: null,
      usage: null,
      started_at: item.created_at,
      completed_at: item.created_at,
      created_at: item.created_at,
      updated_at: item.updated_at,
      duration_ms: 1,
      latest_email_send: null,
    });

    render(<ApprovalsPage />);
    await user.click(
      await screen.findByRole("button", { name: /Jordan Lee/ }),
    );
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    expect(
      await screen.findByRole("heading", { name: "Approve this response?" }),
    ).toBeVisible();
    const dialog = screen
      .getByRole("heading", { name: "Approve this response?" })
      .closest("[data-slot=dialog-content]") as HTMLElement;
    expect(
      within(dialog).getByText(
        /mark it ready to send\. It will NOT send the email automatically/i,
      ),
    ).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(approveMock).toHaveBeenCalledWith("lead-1", "draft-1", {
        expected_revision: 1,
      }),
    );
    expect(sendDraftMock).not.toHaveBeenCalled();
    expect(sendSalesRunMock).not.toHaveBeenCalled();
    expect(
      (await screen.findAllByText(/Approved — ready to send/i)).length,
    ).toBeGreaterThan(0);
  });

  it("rejects a SalesRun-linked draft and leaves pending queue", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const item = approvalItem();
    getApprovalsMock
      .mockResolvedValueOnce(pageOf([item]))
      .mockResolvedValue(
        pageOf([
          approvalItem({
            draft: {
              ...item.draft,
              review_status: "REJECTED",
              revision: 2,
            },
            needs_approval: false,
            can_approve: false,
            can_reject: false,
            can_edit: false,
            can_send: false,
            sales_run: {
              id: "run-1",
              status: "CANCELLED",
              stage: "AWAIT_APPROVAL",
              agent_id: "agent-1",
              agent_name: "Sales Groq Verify",
            },
          }),
        ]),
      );
    rejectMock.mockResolvedValue({
      id: "draft-1",
      lead_id: "lead-1",
      status: "COMPLETED",
      enquiry: item.enquiry,
      response: item.draft.response,
      review_status: "REJECTED",
      revision: 2,
      error: null,
      failure_category: null,
      provider: null,
      model: null,
      usage: null,
      started_at: item.created_at,
      completed_at: item.created_at,
      created_at: item.created_at,
      updated_at: item.updated_at,
      duration_ms: 1,
    });

    render(<ApprovalsPage />);
    await user.click(
      await screen.findByRole("button", { name: /Jordan Lee/ }),
    );
    await user.click(await screen.findByRole("button", { name: "Reject" }));
    const dialog = screen
      .getByRole("heading", { name: "Reject this response?" })
      .closest("[data-slot=dialog-content]") as HTMLElement;
    expect(
      within(dialog).getByText(
        /linked SalesRun waiting for approval will be cancelled/i,
      ),
    ).toBeVisible();
    expect(within(dialog).getByText(/No email will be sent/i)).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "Reject" }));

    await waitFor(() =>
      expect(rejectMock).toHaveBeenCalledWith("lead-1", "draft-1", {
        expected_revision: 1,
        reason: null,
      }),
    );
    await waitFor(() =>
      expect(getApprovalsMock).toHaveBeenCalledWith(
        expect.objectContaining({ status: "rejected" }),
      ),
    );
    expect(screen.getByRole("combobox", { name: "Approval status" })).toHaveValue(
      "rejected",
    );
    expect(
      (await screen.findAllByText(/Response rejected/i)).length,
    ).toBeGreaterThan(0);
  });

  it("edits a draft using expected_revision", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const item = approvalItem();
    getApprovalsMock.mockResolvedValue(pageOf([item]));
    updateMock.mockResolvedValue({
      id: "draft-1",
      lead_id: "lead-1",
      status: "COMPLETED",
      enquiry: item.enquiry,
      response: "Edited reply for Acme.",
      review_status: "EDITED",
      revision: 2,
      error: null,
      failure_category: null,
      provider: null,
      model: null,
      usage: null,
      started_at: item.created_at,
      completed_at: item.created_at,
      created_at: item.created_at,
      updated_at: item.updated_at,
      duration_ms: 1,
    });

    render(<ApprovalsPage />);
    await user.click(
      await screen.findByRole("button", { name: /Jordan Lee/ }),
    );
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const editor = screen.getByLabelText("Edit response");
    await user.clear(editor);
    await user.type(editor, "Edited reply for Acme.");
    await user.click(screen.getByRole("button", { name: "Save edit" }));

    await waitFor(() =>
      expect(updateMock).toHaveBeenCalledWith("lead-1", "draft-1", {
        response: "Edited reply for Acme.",
        expected_revision: 1,
      }),
    );
    expect(
      await screen.findByText(/still needs your review before sending/i),
    ).toBeVisible();
  });

  it("enables send when can_send is true and shows sent state", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const item = approvalItem({
      draft: {
        response: "Thanks for reaching out about a demo. Happy to help.",
        review_status: "APPROVED",
        revision: 2,
        created_at: "2026-09-22T10:00:00Z",
        updated_at: "2026-09-22T10:05:00Z",
      },
      needs_approval: false,
      can_approve: false,
      can_send: true,
    });
    getApprovalsMock.mockResolvedValue(
      pageOf([item]),
    );
    // Force approved filter
    currentSearch = "status=approved&approval=draft-1";
    getSalesRunMock.mockResolvedValue({
      id: "run-1",
      agent_id: "agent-1",
      lead_id: "lead-1",
      status: "WAITING_APPROVAL",
      stage: "AWAIT_APPROVAL",
      qualification_id: null,
      response_draft_id: "draft-1",
      email_send_id: null,
      follow_up_id: null,
      failure_category: null,
      error: null,
      initiated_by_user_id: null,
      revision: 3,
      started_at: item.created_at,
      completed_at: null,
      created_at: item.created_at,
      updated_at: item.updated_at,
    });
    sendSalesRunMock.mockResolvedValue({
      id: "run-1",
      agent_id: "agent-1",
      lead_id: "lead-1",
      status: "COMPLETED",
      stage: "DONE",
      qualification_id: null,
      response_draft_id: "draft-1",
      email_send_id: "send-1",
      follow_up_id: null,
      failure_category: null,
      error: null,
      initiated_by_user_id: null,
      revision: 4,
      started_at: item.created_at,
      completed_at: item.updated_at,
      created_at: item.created_at,
      updated_at: item.updated_at,
      email_send: {
        id: "send-1",
        status: "SENT",
        recipient_email: "jordan@acme.com",
        provider: "fake",
        provider_message_id: "msg",
        draft_revision: 2,
        failure_category: null,
        error: null,
        started_at: item.updated_at,
        completed_at: item.updated_at,
        created_at: item.updated_at,
      },
    });

    render(<ApprovalsPage />);
    expect(
      (await screen.findAllByText("Approved — ready to send")).length,
    ).toBeGreaterThan(0);
    expect(
      await screen.findByRole("button", { name: "Send response" }),
    ).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Send response" }));
    const dialog = screen
      .getByRole("heading", { name: "Send approved response?" })
      .closest("[data-slot=dialog-content]") as HTMLElement;
    expect(
      within(dialog).getByText(
        /send the approved response to the customer/i,
      ),
    ).toBeVisible();
    expect(
      within(dialog).getByText(/human-controlled outbound action/i),
    ).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(sendSalesRunMock).toHaveBeenCalledWith("agent-1", "run-1", {
        expected_revision: 3,
      }),
    );
    expect(sendDraftMock).not.toHaveBeenCalled();
    expect(await screen.findByText("Response sent.")).toBeVisible();
  });

  it("renders standalone draft without inventing an agent", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    getApprovalsMock.mockResolvedValue(
      pageOf([
        approvalItem({
          sales_run: null,
          lead: {
            name: "Pat Solo",
            email: "pat@example.com",
            company: null,
            status: "NEW",
            source: "MANUAL",
          },
        }),
      ]),
    );

    render(<ApprovalsPage />);
    await user.click(await screen.findByRole("button", { name: /Pat Solo/ }));
    const detail = document.querySelector("#approval-detail-pane") as HTMLElement;
    expect(
      within(detail).getByText(/Standalone draft/i),
    ).toBeVisible();
    expect(screen.queryByText("Sales Groq Verify")).not.toBeInTheDocument();
  });

  it("wires search and status filter to the API", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    getApprovalsMock.mockResolvedValue(pageOf([]));
    render(<ApprovalsPage />);
    await screen.findByRole("heading", { name: "You're all caught up." });

    await user.type(
      screen.getByRole("searchbox", { name: "Search approvals" }),
      "Acme",
    );
    await vi.advanceTimersByTimeAsync(350);
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalled();
      expect(getApprovalsMock).toHaveBeenCalledWith(
        expect.objectContaining({ q: "Acme", status: "pending" }),
      );
    });

    await user.selectOptions(screen.getByLabelText("Approval status"), "approved");
    await waitFor(() =>
      expect(getApprovalsMock).toHaveBeenCalledWith(
        expect.objectContaining({ status: "approved" }),
      ),
    );
  });

  it("supports mobile queue/detail navigation", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    getApprovalsMock.mockResolvedValue(pageOf([approvalItem()]));
    render(<ApprovalsPage />);

    const queueButton = await screen.findByRole("button", {
      name: "Approval queue",
    });
    const detailButton = screen.getByRole("button", { name: "Review detail" });
    expect(queueButton).toHaveAttribute("aria-pressed", "true");

    await user.click(detailButton);
    expect(detailButton).toHaveAttribute("aria-pressed", "true");
    await user.click(
      screen.getByRole("button", { name: "Back to approval queue" }),
    );
    expect(queueButton).toHaveAttribute("aria-pressed", "true");
  });

  it("does not invent risk metrics", async () => {
    render(<ApprovalsPage />);
    expect(screen.queryByText("High-risk actions")).not.toBeInTheDocument();
    expect(screen.queryByText("High risk")).not.toBeInTheDocument();
    expect(
      (await screen.findAllByRole("heading", { name: "Needs your review" }))
        .length,
    ).toBeGreaterThan(0);
  });

  it("paginates with limit and offset", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const firstPage = {
      items: [approvalItem({ draft_id: "draft-page-1" })],
      limit: 20,
      offset: 0,
      total: 40,
    };
    const secondPage = {
      items: [approvalItem({ draft_id: "draft-page-2", lead_id: "lead-2" })],
      limit: 20,
      offset: 20,
      total: 40,
    };
    getApprovalsMock
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce(secondPage)
      .mockResolvedValue(firstPage);

    render(<ApprovalsPage />);
    await waitFor(() =>
      expect(getApprovalsMock).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 20, offset: 0 }),
      ),
    );
    expect(await screen.findByText(/Showing 1–1 of 40/)).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(getApprovalsMock).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 20, offset: 20 }),
      ),
    );

    await user.click(await screen.findByRole("button", { name: "Previous" }));
    await waitFor(() =>
      expect(getApprovalsMock).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 20, offset: 0 }),
      ),
    );
  });

  it("shows send failure without marking the approval as sent", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const item = approvalItem({
      draft: {
        response: "Thanks for reaching out about a demo. Happy to help.",
        review_status: "APPROVED",
        revision: 2,
        created_at: "2026-09-22T10:00:00Z",
        updated_at: "2026-09-22T10:05:00Z",
      },
      needs_approval: false,
      can_approve: false,
      can_send: true,
    });
    currentSearch = "status=approved&approval=draft-1";
    getApprovalsMock.mockResolvedValue(pageOf([item]));
    getSalesRunMock.mockResolvedValue({
      id: "run-1",
      agent_id: "agent-1",
      lead_id: "lead-1",
      status: "WAITING_APPROVAL",
      stage: "AWAIT_APPROVAL",
      qualification_id: null,
      response_draft_id: "draft-1",
      email_send_id: null,
      follow_up_id: null,
      failure_category: null,
      error: null,
      initiated_by_user_id: null,
      revision: 3,
      started_at: item.created_at,
      completed_at: null,
      created_at: item.created_at,
      updated_at: item.updated_at,
    });
    sendSalesRunMock.mockRejectedValue(
      new ApiError("provider failed", 502, { detail: "upstream failed" }),
    );

    render(<ApprovalsPage />);
    await user.click(await screen.findByRole("button", { name: "Send response" }));
    const dialog = screen
      .getByRole("heading", { name: "Send approved response?" })
      .closest("[data-slot=dialog-content]") as HTMLElement;
    await user.click(within(dialog).getByRole("button", { name: "Send" }));

    expect(
      await screen.findByText("The email provider could not send this message."),
    ).toBeVisible();
    expect(screen.queryByText("Response sent.")).not.toBeInTheDocument();
    expect(
      screen.getAllByText(/Approved — ready to send/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Send response" })).toBeEnabled();
  });

  it("sends standalone drafts through sendLeadResponseDraft", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const item = approvalItem({
      sales_run: null,
      draft: {
        response: "Thanks for writing.",
        review_status: "APPROVED",
        revision: 2,
        created_at: "2026-09-22T10:00:00Z",
        updated_at: "2026-09-22T10:05:00Z",
      },
      needs_approval: false,
      can_approve: false,
      can_send: true,
    });
    const sentItem = approvalItem({
      ...item,
      email: { status: "SENT", sent_at: item.updated_at },
      can_send: false,
    });
    currentSearch = "status=approved&approval=draft-1";
    getApprovalsMock.mockResolvedValue(pageOf([item]));
    sendDraftMock.mockImplementation(async () => {
      getApprovalsMock.mockResolvedValue(pageOf([sentItem]));
      return {
        id: "send-1",
        lead_id: "lead-1",
        response_draft_id: "draft-1",
        status: "SENT",
        recipient_email: "jordan@acme.com",
        sender_email: "noreply@example.com",
        subject: "Re: Your enquiry",
        body_text: "Thanks for writing.",
        draft_revision: 2,
        provider: "fake",
        provider_message_id: "msg-1",
        error: null,
        failure_category: null,
        started_at: item.updated_at,
        completed_at: item.updated_at,
        created_at: item.updated_at,
        duration_ms: 10,
      };
    });

    render(<ApprovalsPage />);
    await user.click(await screen.findByRole("button", { name: "Send response" }));
    const dialog = screen
      .getByRole("heading", { name: "Send approved response?" })
      .closest("[data-slot=dialog-content]") as HTMLElement;
    await user.click(within(dialog).getByRole("button", { name: "Send" }));

    await waitFor(() =>
      expect(sendDraftMock).toHaveBeenCalledWith("lead-1", "draft-1"),
    );
    expect(sendSalesRunMock).not.toHaveBeenCalled();
    expect(getSalesRunMock).not.toHaveBeenCalled();
    expect(await screen.findByText("Response sent.")).toBeVisible();
    expect(
      (await screen.findAllByText("Response sent")).length,
    ).toBeGreaterThan(0);
  });
});
