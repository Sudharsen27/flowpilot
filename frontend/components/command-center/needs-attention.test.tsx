import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NeedsAttention } from "@/components/command-center/needs-attention";
import { ApiError } from "@/lib/api/client";
import {
  getFollowUpOperations,
  getLead,
  getLeadFollowUps,
  getLeadResponseDraft,
} from "@/lib/api/leads";
import {
  cancelSalesRun,
  listOrganizationSalesRuns,
  sendSalesRun,
} from "@/lib/api/sales-runs";
import type {
  FollowUpOperationsItem,
  FollowUpOperationsResponse,
  Lead,
  SalesRun,
} from "@/types/api";

vi.mock("@/lib/api/sales-runs", () => ({
  listOrganizationSalesRuns: vi.fn(),
  cancelSalesRun: vi.fn(),
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

const listOrganizationSalesRunsMock = vi.mocked(listOrganizationSalesRuns);
const cancelSalesRunMock = vi.mocked(cancelSalesRun);
const sendSalesRunMock = vi.mocked(sendSalesRun);
const getFollowUpOperationsMock = vi.mocked(getFollowUpOperations);
const getLeadMock = vi.mocked(getLead);
const getLeadFollowUpsMock = vi.mocked(getLeadFollowUps);
const getLeadResponseDraftMock = vi.mocked(getLeadResponseDraft);

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
    listOrganizationSalesRunsMock.mockReset();
    cancelSalesRunMock.mockReset();
    sendSalesRunMock.mockReset();
    getFollowUpOperationsMock.mockReset();
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
    listOrganizationSalesRunsMock.mockImplementation(async (params = {}) => {
      if (params.status === "WAITING_APPROVAL") return salesPage([]);
      if (params.status === "FAILED") return salesPage([]);
      return salesPage([]);
    });
    getFollowUpOperationsMock.mockResolvedValue(emptyFollowUps());
  });

  it("shows empty copy for each queue and does not invent activity", async () => {
    render(<NeedsAttention />);
    expect(
      await screen.findByText("Nothing waiting for review"),
    ).toBeVisible();
    expect(screen.getByText("No failed sends")).toBeVisible();
    expect(screen.getByText("No overdue follow-ups")).toBeVisible();
    expect(screen.queryByText("SECRET ENQUIRY BODY")).not.toBeInTheDocument();
    expect(
      screen.getByText(/Completed work is not listed here/),
    ).toBeVisible();
  });

  it("lists waiting runs and opens the existing draft dialog", async () => {
    const user = userEvent.setup();
    listOrganizationSalesRunsMock.mockImplementation(async (params = {}) => {
      if (params.status === "WAITING_APPROVAL") return salesPage([run()]);
      return salesPage([]);
    });
    render(<NeedsAttention />);
    expect((await screen.findAllByText("Ada Prospect")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Generated").length).toBeGreaterThan(0);
    expect(screen.queryByText("SECRET ENQUIRY BODY")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Send approved response" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Review draft" })[0]!);
    expect(getLeadMock).toHaveBeenCalledWith("lead-1");
    expect(await screen.findByText("Draft response")).toBeVisible();
  });

  it("sends an approved waiting run after confirmation and refetches", async () => {
    const user = userEvent.setup();
    const approved = run({
      response_draft: { id: "draft-1", status: "COMPLETED", review_status: "APPROVED" },
    });
    let sent = false;
    listOrganizationSalesRunsMock.mockImplementation(async (params = {}) => {
      if (params.status === "WAITING_APPROVAL" && !sent) {
        return salesPage([approved]);
      }
      return salesPage([]);
    });
    sendSalesRunMock.mockImplementation(async () => {
      sent = true;
      return run({ status: "COMPLETED", stage: "DONE" });
    });
    render(<NeedsAttention />);
    await user.click(
      (await screen.findAllByRole("button", { name: "Send approved response" }))[0]!,
    );
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
    await waitFor(() =>
      expect(screen.getByText("Nothing waiting for review")).toBeVisible(),
    );
  });

  it("keeps a conflict visible and does not remove the row", async () => {
    const user = userEvent.setup();
    const approved = run({
      response_draft: { id: "draft-1", status: "COMPLETED", review_status: "APPROVED" },
    });
    listOrganizationSalesRunsMock.mockImplementation(async (params = {}) => {
      if (params.status === "WAITING_APPROVAL") return salesPage([approved]);
      return salesPage([]);
    });
    sendSalesRunMock.mockRejectedValue(
      new ApiError("Conflict", 409, {
        detail: "A send is already in progress for this draft.",
      }),
    );
    render(<NeedsAttention />);
    await user.click(
      (await screen.findAllByRole("button", { name: "Send approved response" }))[0]!,
    );
    expect(await screen.findByText("Thanks for reaching out.")).toBeVisible();
    await user.click(
      screen.getAllByRole("button", { name: "Send approved response" }).at(-1)!,
    );
    expect(
      await screen.findByText("A send is already in progress for this draft."),
    ).toBeVisible();
    expect(screen.getAllByText("Ada Prospect").length).toBeGreaterThan(0);
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
      if (params.status === "WAITING_APPROVAL") return salesPage([]);
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

  it("cancels a waiting run after confirmation", async () => {
    const user = userEvent.setup();
    let cancelled = false;
    listOrganizationSalesRunsMock.mockImplementation(async (params = {}) => {
      if (params.status === "WAITING_APPROVAL" && !cancelled) {
        return salesPage([run()]);
      }
      return salesPage([]);
    });
    cancelSalesRunMock.mockImplementation(async () => {
      cancelled = true;
      return run({ status: "CANCELLED" });
    });
    render(<NeedsAttention />);
    await user.click((await screen.findAllByRole("button", { name: "Cancel run" }))[0]!);
    expect(screen.getByText("Cancel sales run")).toBeVisible();
    await user.click(screen.getAllByRole("button", { name: "Cancel run" }).at(-1)!);
    await waitFor(() =>
      expect(cancelSalesRunMock).toHaveBeenCalledWith("agent-1", "run-1", {
        expected_revision: 2,
      }),
    );
  });
});
