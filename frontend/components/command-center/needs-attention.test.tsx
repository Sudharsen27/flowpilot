import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NeedsAttention } from "@/components/command-center/needs-attention";
import { getApprovals } from "@/lib/api/approvals";
import { ApiError } from "@/lib/api/client";
import { getInbox } from "@/lib/api/inbox";
import {
  getFollowUpOperations,
  getLead,
  getLeadFollowUps,
  getLeadResponseDraft,
} from "@/lib/api/leads";
import {
  listOrganizationSalesRuns,
  sendSalesRun,
} from "@/lib/api/sales-runs";
import type {
  ApprovalListResponse,
  ApprovalQueueItem,
  FollowUpOperationsItem,
  FollowUpOperationsResponse,
  InboxItem,
  Lead,
  SalesRun,
} from "@/types/api";

vi.mock("@/lib/api/approvals", () => ({
  getApprovals: vi.fn(),
}));

vi.mock("@/lib/api/inbox", () => ({
  getInbox: vi.fn(),
}));

vi.mock("@/lib/api/sales-runs", () => ({
  listOrganizationSalesRuns: vi.fn(),
  sendSalesRun: vi.fn(),
}));

vi.mock("@/lib/api/leads", () => ({
  getFollowUpOperations: vi.fn(),
  getLead: vi.fn(),
  getLeadFollowUps: vi.fn(),
  getLeadResponseDraft: vi.fn(),
  generateLeadResponseDraft: vi.fn(),
  updateLeadResponseDraft: vi.fn(),
  approveLeadResponseDraft: vi.fn(),
  rejectLeadResponseDraft: vi.fn(),
  sendLeadResponseDraft: vi.fn(),
  createLeadFollowUp: vi.fn(),
  updateLeadFollowUp: vi.fn(),
  completeLeadFollowUp: vi.fn(),
  cancelLeadFollowUp: vi.fn(),
}));

const getApprovalsMock = vi.mocked(getApprovals);
const listOrganizationSalesRunsMock = vi.mocked(listOrganizationSalesRuns);
const sendSalesRunMock = vi.mocked(sendSalesRun);
const getFollowUpOperationsMock = vi.mocked(getFollowUpOperations);
const getLeadMock = vi.mocked(getLead);
const getLeadFollowUpsMock = vi.mocked(getLeadFollowUps);
const getLeadResponseDraftMock = vi.mocked(getLeadResponseDraft);
const getInboxMock = vi.mocked(getInbox);

function emptyInbox() {
  return {
    items: [] as InboxItem[],
    limit: 20,
    offset: 0,
    total: 0,
    state_counts: { OPEN: 0, NEEDS_APPROVAL: 0, CLOSED: 0 },
    needs_approval_count: 0,
    human_attention_count: 0,
  };
}

const lead: Lead = {
  id: "lead-1",
  name: "Ada Prospect",
  email: "ada@example.com",
  phone: null,
  company: null,
  source: "WEBSITE",
  status: "NEW",
  notes: null,
  created_at: "2026-09-11T10:00:00Z",
  updated_at: "2026-09-11T10:00:00Z",
};

function run(overrides: Partial<SalesRun> = {}): SalesRun {
  return {
    id: "run-1",
    agent_id: "agent-1",
    lead_id: "lead-1",
    status: "WAITING_APPROVAL",
    stage: "AWAIT_APPROVAL",
    qualification_id: "q-1",
    response_draft_id: "draft-1",
    email_send_id: null,
    follow_up_id: null,
    failure_category: null,
    error: null,
    initiated_by_user_id: "user-1",
    revision: 2,
    started_at: "2026-09-11T10:00:00Z",
    completed_at: null,
    created_at: "2026-09-11T10:00:00Z",
    updated_at: "2026-09-11T10:00:01Z",
    enquiry: "SECRET ENQUIRY BODY",
    lead: {
      id: "lead-1",
      name: "Ada Prospect",
      email: "ada@example.com",
      status: "NEW",
    },
    response_draft: {
      id: "draft-1",
      status: "COMPLETED",
      review_status: "GENERATED",
    },
    ...overrides,
  };
}

function salesPage(items: SalesRun[], total = items.length) {
  return { items, limit: 20, offset: 0, total };
}

function approvalItem(
  overrides: Partial<ApprovalQueueItem> = {},
): ApprovalQueueItem {
  return {
    draft_id: "draft-1",
    lead_id: "lead-1",
    lead: {
      name: "Ada Prospect",
      email: "ada@example.com",
      company: null,
      status: "NEW",
      source: "WEBSITE",
    },
    enquiry: "SECRET ENQUIRY BODY",
    draft: {
      response: "SECRET DRAFT TEXT",
      review_status: "GENERATED",
      revision: 1,
      created_at: "2026-09-11T10:00:00Z",
      updated_at: "2026-09-11T10:00:01Z",
    },
    sales_run: {
      id: "run-1",
      status: "WAITING_APPROVAL",
      stage: "AWAIT_APPROVAL",
      agent_id: "agent-1",
      agent_name: "Inbound qualifier",
    },
    email: null,
    needs_approval: true,
    can_approve: true,
    can_reject: true,
    can_edit: true,
    can_send: false,
    created_at: "2026-09-11T10:00:00Z",
    updated_at: "2026-09-11T10:00:01Z",
    ...overrides,
  };
}

function approvalPage(
  items: ApprovalQueueItem[],
  total = items.length,
): ApprovalListResponse {
  return { items, limit: 20, offset: 0, total };
}

function followUpItem(
  overrides: Partial<FollowUpOperationsItem> = {},
): FollowUpOperationsItem {
  return {
    follow_up: {
      id: "fu-1",
      lead_id: "lead-1",
      type: "EMAIL_FOLLOW_UP",
      status: "PENDING",
      due_at: "2026-09-08T09:00:00Z",
      revision: 1,
      is_overdue: true,
      completed_at: null,
      cancelled_at: null,
      created_at: "2026-09-01T09:00:00Z",
      updated_at: "2026-09-01T09:00:00Z",
    },
    lead: {
      id: "lead-1",
      name: "Cai Wong",
      email: "cai@example.com",
    },
    latest_execution: null,
    ...overrides,
  };
}

function followUpPage(
  items: FollowUpOperationsItem[],
  total = items.length,
): FollowUpOperationsResponse {
  return {
    items,
    summary: {
      overdue: total,
      due_today: 0,
      upcoming: 0,
      completed: 0,
      cancelled: 0,
    },
    limit: 20,
    offset: 0,
    total,
  };
}

function emptyFollowUps() {
  return followUpPage([]);
}

describe("NeedsAttention", () => {
  beforeEach(() => {
    getApprovalsMock.mockReset();
    listOrganizationSalesRunsMock.mockReset();
    sendSalesRunMock.mockReset();
    getFollowUpOperationsMock.mockReset();
    getInboxMock.mockReset();
    getLeadMock.mockReset();
    getLeadFollowUpsMock.mockReset();
    getLeadResponseDraftMock.mockReset();
    getLeadMock.mockResolvedValue(lead);
    getLeadFollowUpsMock.mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      total: 0,
    });
    getLeadResponseDraftMock.mockResolvedValue({
      id: "draft-1",
      lead_id: "lead-1",
      status: "COMPLETED",
      enquiry: "Need a demo",
      original_response: "Thanks for reaching out.",
      response: "Thanks for reaching out.",
      human_edited: false,
      review_status: "GENERATED",
      reviewed_by_user_id: null,
      reviewed_at: null,
      rejection_reason: null,
      revision: 1,
      error: null,
      failure_category: null,
      provider: "fake",
      model: "fake",
      usage: null,
      started_at: "2026-09-11T10:00:00Z",
      completed_at: "2026-09-11T10:00:01Z",
      created_at: "2026-09-11T10:00:00Z",
      updated_at: "2026-09-11T10:00:01Z",
      duration_ms: 1000,
      latest_email_send: null,
    });
    getApprovalsMock.mockResolvedValue(approvalPage([]));
    listOrganizationSalesRunsMock.mockImplementation(async (params = {}) => {
      if (params.status === "FAILED") return salesPage([]);
      return salesPage([]);
    });
    getFollowUpOperationsMock.mockResolvedValue(emptyFollowUps());
    getInboxMock.mockResolvedValue(emptyInbox());
  });

  it("shows empty copy for each queue and does not invent activity", async () => {
    render(<NeedsAttention />);
    expect(
      await screen.findByText("Nothing waiting for review"),
    ).toBeVisible();
    expect(screen.getByText("No failed sends")).toBeVisible();
    expect(screen.getByText("No overdue follow-ups")).toBeVisible();
    expect(
      screen.getByText("No leads currently require human attention."),
    ).toBeVisible();
    expect(screen.queryByText("SECRET ENQUIRY BODY")).not.toBeInTheDocument();
    expect(
      screen.getByText(/Completed work is not listed here/),
    ).toBeVisible();
  });

  it("lists standalone and sales-run drafts once and deep-links by draft_id", async () => {
    getApprovalsMock.mockResolvedValue(
      approvalPage(
        [
          approvalItem({
            draft_id: "draft-standalone",
            lead_id: "lead-2",
            sales_run: null,
            lead: {
              name: "Bea Copilot",
              email: "bea@example.com",
              company: null,
              status: "NEW",
              source: "MANUAL",
            },
          }),
          approvalItem(),
          approvalItem({ draft_id: "draft-1", enquiry: "SECOND COPY" }),
        ],
        2,
      ),
    );
    render(<NeedsAttention />);

    const links = await screen.findAllByRole("link", { name: "Review draft" });
    expect([...new Set(links.map((link) => link.getAttribute("href")))]).toEqual([
      "/approvals?approval=draft-standalone",
      "/approvals?approval=draft-1",
    ]);
    expect(screen.getAllByText("Bea Copilot").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Ada Prospect").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sales Copilot").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sales run").length).toBeGreaterThan(0);
    expect(screen.getByText("2 waiting")).toBeVisible();
    expect(screen.queryByText("SECRET ENQUIRY BODY")).not.toBeInTheDocument();
    expect(screen.queryByText("SECRET DRAFT TEXT")).not.toBeInTheDocument();
    expect(screen.queryByText("SECOND COPY")).not.toBeInTheDocument();
    expect(getApprovalsMock).toHaveBeenCalledWith({
      status: "pending",
      limit: 20,
      offset: 0,
    });
    expect(listOrganizationSalesRunsMock).not.toHaveBeenCalledWith(
      expect.objectContaining({ status: "WAITING_APPROVAL" }),
    );
  });

  it("retries a failed send after confirmation and refetches", async () => {
    const user = userEvent.setup();
    const approved = run({
      status: "FAILED",
      stage: "SEND",
      response_draft: { id: "draft-1", status: "COMPLETED", review_status: "APPROVED" },
    });
    let sent = false;
    listOrganizationSalesRunsMock.mockImplementation(async (params = {}) => {
      if (params.status === "FAILED" && params.stage === "SEND" && !sent) {
        return salesPage([approved]);
      }
      return salesPage([]);
    });
    sendSalesRunMock.mockImplementation(async () => {
      sent = true;
      return run({ status: "COMPLETED", stage: "DONE" });
    });
    render(<NeedsAttention />);
    await user.click((await screen.findAllByRole("button", { name: "Retry send" }))[0]!);
    expect(await screen.findByText("Send approved response?")).toBeVisible();
    expect(await screen.findByText("Thanks for reaching out.")).toBeVisible();
    await user.click(
      screen.getAllByRole("button", { name: "Send approved response" }).at(-1)!,
    );
    await waitFor(() =>
      expect(sendSalesRunMock).toHaveBeenCalledWith("agent-1", "run-1", {
        expected_revision: 2,
      }),
    );
    await waitFor(() => expect(screen.getByText("No failed sends")).toBeVisible());
    expect(screen.getByText("Nothing waiting for review")).toBeVisible();
  });

  it("keeps a failed-send conflict visible and does not remove the row", async () => {
    const user = userEvent.setup();
    const approved = run({
      status: "FAILED",
      stage: "SEND",
      response_draft: { id: "draft-1", status: "COMPLETED", review_status: "APPROVED" },
    });
    listOrganizationSalesRunsMock.mockImplementation(async (params = {}) => {
      if (params.status === "FAILED" && params.stage === "SEND") {
        return salesPage([approved]);
      }
      return salesPage([]);
    });
    sendSalesRunMock.mockRejectedValue(
      new ApiError("Conflict", 409, {
        detail: "A send is already in progress for this draft.",
      }),
    );
    render(<NeedsAttention />);
    await user.click((await screen.findAllByRole("button", { name: "Retry send" }))[0]!);
    expect(await screen.findByText("Thanks for reaching out.")).toBeVisible();
    await user.click(
      screen.getAllByRole("button", { name: "Send approved response" }).at(-1)!,
    );
    expect(
      await screen.findByText("A send is already in progress for this draft."),
    ).toBeVisible();
    expect(screen.getAllByText("Ada Prospect").length).toBeGreaterThan(0);
    expect(screen.getByText("Nothing waiting for review")).toBeVisible();
  });

  it("lists failed sends and omits AI qualification failures", async () => {
    listOrganizationSalesRunsMock.mockImplementation(async (params = {}) => {
      if (params.status === "FAILED" && params.stage === "SEND") {
        return salesPage([
          run({
            id: "run-send",
            status: "FAILED",
            stage: "SEND",
            error: "Provider timeout",
            response_draft: {
              id: "draft-1",
              status: "COMPLETED",
              review_status: "APPROVED",
            },
          }),
        ]);
      }
      return salesPage([]);
    });
    render(<NeedsAttention />);
    expect((await screen.findAllByText("Provider timeout")).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "Retry send" }).length).toBeGreaterThan(0);
    expect(screen.queryByText("AI provider request failed")).not.toBeInTheDocument();
  });

  it("opens follow-up management for overdue items", async () => {
    const user = userEvent.setup();
    getFollowUpOperationsMock.mockResolvedValue(followUpPage([followUpItem()]));
    render(<NeedsAttention />);
    expect((await screen.findAllByText("Cai Wong")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Overdue").length).toBeGreaterThan(0);
    await user.click(screen.getAllByRole("button", { name: "Manage" })[0]!);
    expect(getLeadMock).toHaveBeenCalledWith("lead-1");
    expect(await screen.findByText("Follow-ups")).toBeVisible();
  });

  it("retries a failed queue independently of the others", async () => {
    const user = userEvent.setup();
    listOrganizationSalesRunsMock.mockImplementation(async (params = {}) => {
      if (params.status === "FAILED") {
        throw new ApiError("Down", 500, { detail: "unavailable" });
      }
      return salesPage([]);
    });
    render(<NeedsAttention />);
    expect(
      await screen.findByText("Failed sends could not be loaded."),
    ).toBeVisible();
    expect(screen.getByText("Nothing waiting for review")).toBeVisible();
    expect(screen.getByText("No overdue follow-ups")).toBeVisible();
    listOrganizationSalesRunsMock.mockImplementation(async (params = {}) => {
      if (params.status === "FAILED" && params.stage === "SEND") {
        return salesPage([
          run({ id: "run-send", status: "FAILED", stage: "SEND", error: "Provider timeout" }),
        ]);
      }
      return salesPage([]);
    });
    const failedSection = screen.getByRole("heading", { name: "Failed sends" }).closest("section");
    expect(failedSection).toBeTruthy();
    await user.click(within(failedSection!).getByRole("button", { name: "Retry" }));
    expect((await screen.findAllByText("Provider timeout")).length).toBeGreaterThan(0);
  });

  it("lists leads that require human attention and opens the lead page", async () => {
    const item: InboxItem = {
      lead_id: "lead-9",
      name: "Nia Cole",
      email: "nia@example.com",
      company: null,
      source: "WEBSITE",
      lead_status: "NEW",
      human_attention_required: true,
      conversation_state: "OPEN",
      needs_approval: false,
      last_activity_at: "2026-09-22T11:58:00Z",
      last_activity_type: "AI_ACTION",
      last_activity_title: "Human attention required",
      preview: null,
      latest_draft: null,
      latest_email_status: null,
      latest_sales_run: null,
      latest_follow_up_status: null,
      latest_follow_up_overdue: null,
    };
    getInboxMock.mockResolvedValue({
      ...emptyInbox(),
      items: [item],
      total: 1,
      human_attention_count: 1,
    });
    render(<NeedsAttention />);
    const link = await screen.findByRole("link", { name: /Nia Cole/ });
    expect(link).toHaveAttribute("href", "/leads/lead-9");
    expect(getInboxMock).toHaveBeenCalledWith({
      human_attention_required: true,
      limit: 20,
      offset: 0,
    });
  });
});
