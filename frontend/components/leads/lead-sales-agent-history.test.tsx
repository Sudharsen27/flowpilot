import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LeadSalesAgentHistory } from "@/components/leads/lead-sales-agent-history";
import { ApiError } from "@/lib/api/client";
import {
  getLeadFollowUp,
  getLeadQualification,
  getLeadResponseDraft,
} from "@/lib/api/leads";
import { getSalesRun, listLeadSalesRuns } from "@/lib/api/sales-runs";
import type { Lead, LeadQualificationResult, LeadResponseDraftResult, SalesRun } from "@/types/api";

vi.mock("@/lib/api/leads", () => ({
  getLeadFollowUp: vi.fn(),
  getLeadQualification: vi.fn(),
  getLeadResponseDraft: vi.fn(),
}));

vi.mock("@/lib/api/sales-runs", () => ({
  getSalesRun: vi.fn(),
  listLeadSalesRuns: vi.fn(),
}));

const listLeadSalesRunsMock = vi.mocked(listLeadSalesRuns);
const getSalesRunMock = vi.mocked(getSalesRun);
const getLeadQualificationMock = vi.mocked(getLeadQualification);
const getLeadResponseDraftMock = vi.mocked(getLeadResponseDraft);
const getLeadFollowUpMock = vi.mocked(getLeadFollowUp);

const lead: Lead = {
  id: "lead-1",
  name: "Ada Prospect",
  email: "ada@example.com",
  phone: null,
  company: null,
  source: "WEBSITE",
  status: "NEW",
  notes: null,
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-10T10:00:00Z",
};

function run(overrides: Partial<SalesRun> = {}): SalesRun {
  return {
    id: "run-1",
    agent_id: "agent-1",
    lead_id: "lead-1",
    status: "WAITING_APPROVAL",
    stage: "AWAIT_APPROVAL",
    qualification_id: "q-1",
    response_draft_id: "d-1",
    email_send_id: null,
    follow_up_id: null,
    failure_category: null,
    error: null,
    initiated_by_user_id: null,
    revision: 1,
    started_at: "2026-09-10T10:00:00Z",
    completed_at: null,
    created_at: "2026-09-10T10:00:00Z",
    updated_at: "2026-09-10T10:00:01Z",
    enquiry: null,
    ...overrides,
  };
}

function page(items: SalesRun[], overrides: { total?: number; offset?: number } = {}) {
  return {
    items,
    limit: 20,
    offset: overrides.offset ?? 0,
    total: overrides.total ?? items.length,
  };
}

function qualification(): LeadQualificationResult {
  return {
    id: "q-1",
    lead_id: "lead-1",
    status: "COMPLETED",
    enquiry: "Need a demo",
    analysis: {
      summary: "The sender asked for a demo.",
      intent: "REQUEST_DEMO",
      qualification: "NEEDS_MORE_INFORMATION",
      qualification_reasons: ["Budget is not stated"],
      confidence: 0.62,
      extracted_contact: { name: null, email: null, phone: null },
      extracted_company: { name: null },
      buying_signals: ["Asked to schedule a demo"],
      missing_information: ["Contact email"],
    },
    error: null,
    failure_category: null,
    provider: "fake",
    model: "fake-model",
    usage: { total_tokens: 18 },
    started_at: "2026-09-10T10:00:00Z",
    completed_at: "2026-09-10T10:00:01Z",
    created_at: "2026-09-10T10:00:00Z",
    duration_ms: 1000,
  };
}

function draft(overrides: Partial<LeadResponseDraftResult> = {}): LeadResponseDraftResult {
  return {
    id: "d-1",
    lead_id: "lead-1",
    status: "COMPLETED",
    enquiry: "Need a demo",
    original_response: "Thanks for reaching out.",
    response: "Thanks for reaching out.",
    human_edited: false,
    review_status: "APPROVED",
    reviewed_by_user_id: "user-1",
    reviewed_at: "2026-09-10T10:05:00Z",
    rejection_reason: null,
    revision: 2,
    error: null,
    failure_category: null,
    provider: "fake",
    model: "fake-model",
    usage: { total_tokens: 20 },
    started_at: "2026-09-10T10:00:00Z",
    completed_at: "2026-09-10T10:00:01Z",
    created_at: "2026-09-10T10:00:00Z",
    updated_at: "2026-09-10T10:05:00Z",
    duration_ms: 1000,
    latest_email_send: {
      id: "send-1",
      lead_id: "lead-1",
      response_draft_id: "d-1",
      status: "SENT",
      recipient_email: "ada@example.com",
      sender_email: "noreply@example.com",
      subject: "Re: Your enquiry",
      body_text: "Thanks for reaching out.",
      draft_revision: 2,
      provider: "resend",
      provider_message_id: "msg-1",
      error: null,
      failure_category: null,
      started_at: "2026-09-10T11:00:00Z",
      completed_at: "2026-09-10T11:00:01Z",
      created_at: "2026-09-10T11:00:00Z",
      duration_ms: 1000,
    },
    ...overrides,
  };
}

describe("LeadSalesAgentHistory", () => {
  beforeEach(() => {
    listLeadSalesRunsMock.mockReset();
    getSalesRunMock.mockReset();
    getLeadQualificationMock.mockReset();
    getLeadResponseDraftMock.mockReset();
    getLeadFollowUpMock.mockReset();
  });

  it("shows loading then empty history", async () => {
    listLeadSalesRunsMock.mockReturnValue(new Promise(() => undefined));
    render(<LeadSalesAgentHistory open lead={lead} onOpenChange={() => undefined} />);
    expect(screen.getAllByText("Loading records").length).toBeGreaterThan(0);
  });

  it("shows empty history without fabricating rows", async () => {
    listLeadSalesRunsMock.mockResolvedValue(page([]));
    render(<LeadSalesAgentHistory open lead={lead} onOpenChange={() => undefined} />);
    expect(
      await screen.findByRole("heading", { name: "No Sales Agent runs" }),
    ).toBeVisible();
    expect(screen.queryByText("Example")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "View run" })).not.toBeInTheDocument();
  });

  it("shows an error and retries the list", async () => {
    const user = userEvent.setup();
    listLeadSalesRunsMock
      .mockRejectedValueOnce(new ApiError("boom", 500))
      .mockResolvedValue(page([]));
    render(<LeadSalesAgentHistory open lead={lead} onOpenChange={() => undefined} />);
    expect(
      await screen.findByRole("heading", {
        name: "Sales Agent history could not be loaded",
      }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "No Sales Agent runs" }),
    ).toBeVisible();
    expect(listLeadSalesRunsMock).toHaveBeenCalledTimes(2);
  });

  it("paginates sales run history", async () => {
    const user = userEvent.setup();
    const first = run({ id: "run-1" });
    const second = run({ id: "run-2", created_at: "2026-08-01T10:00:00Z" });
    listLeadSalesRunsMock
      .mockResolvedValueOnce(page([first], { total: 21, offset: 0 }))
      .mockResolvedValueOnce(page([second], { total: 21, offset: 20 }));
    render(<LeadSalesAgentHistory open lead={lead} onOpenChange={() => undefined} />);
    expect(await screen.findByText("Showing 1–20 of 21")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(listLeadSalesRunsMock).toHaveBeenLastCalledWith("lead-1", {
        limit: 20,
        offset: 20,
      }),
    );
    expect(await screen.findByText("Showing 21–21 of 21")).toBeVisible();
  });

  it("loads run detail from existing APIs and does not invent missing records", async () => {
    const user = userEvent.setup();
    const listed = run({
      enquiry: null,
      email_send: {
        id: "send-1",
        status: "SENT",
        recipient_email: "ada@example.com",
        provider: "resend",
        provider_message_id: "msg-1",
        draft_revision: 2,
        failure_category: null,
        error: null,
        started_at: "2026-09-10T11:00:00Z",
        completed_at: "2026-09-10T11:00:01Z",
        created_at: "2026-09-10T11:00:00Z",
      },
      follow_up: {
        id: "fu-1",
        type: "EMAIL_FOLLOW_UP",
        status: "PENDING",
        due_at: "2026-09-20T12:00:00Z",
        is_overdue: false,
      },
      follow_up_id: "fu-1",
      email_send_id: "send-1",
    });
    listLeadSalesRunsMock.mockResolvedValue(page([listed]));
    getSalesRunMock.mockResolvedValue({
      ...listed,
      enquiry: "Need a demo next week",
    });
    getLeadQualificationMock.mockResolvedValue(qualification());
    getLeadResponseDraftMock.mockResolvedValue(draft());
    getLeadFollowUpMock.mockResolvedValue({
      id: "fu-1",
      lead_id: "lead-1",
      email_send_id: "send-1",
      type: "EMAIL_FOLLOW_UP",
      status: "PENDING",
      due_at: "2026-09-20T12:00:00Z",
      notes: null,
      body_text: "SECRET FOLLOW-UP BODY",
      revision: 1,
      is_overdue: false,
      completed_at: null,
      cancelled_at: null,
      created_at: "2026-09-10T12:00:00Z",
      updated_at: "2026-09-10T12:00:00Z",
    });
    render(<LeadSalesAgentHistory open lead={lead} onOpenChange={() => undefined} />);
    expect((await screen.findAllByText("Waiting for approval")).length).toBeGreaterThan(0);
    expect(screen.queryByText("Need a demo next week")).not.toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "View run" })[0]!);
    expect(await screen.findByText("Need a demo next week")).toBeVisible();
    expect(screen.getByText("The sender asked for a demo.")).toBeVisible();
    expect(screen.getAllByText("Thanks for reaching out.").length).toBeGreaterThan(0);
    expect(screen.getByText("SENT")).toBeVisible();
    expect(screen.getByText("Email follow-up")).toBeVisible();
    expect(screen.queryByText("SECRET FOLLOW-UP BODY")).not.toBeInTheDocument();
    expect(getSalesRunMock).toHaveBeenCalledWith("agent-1", "run-1");
    expect(getLeadQualificationMock).toHaveBeenCalledWith("lead-1", "q-1");
    expect(getLeadResponseDraftMock).toHaveBeenCalledWith("lead-1", "d-1");
    expect(getLeadFollowUpMock).toHaveBeenCalledWith("lead-1", "fu-1");
  });

  it("states missing linked records for a selected run", async () => {
    const user = userEvent.setup();
    const listed = run({
      qualification_id: null,
      response_draft_id: null,
      email_send_id: null,
      follow_up_id: null,
      email_send: null,
      follow_up: null,
    });
    listLeadSalesRunsMock.mockResolvedValue(page([listed]));
    getSalesRunMock.mockResolvedValue({ ...listed, enquiry: "Need a demo" });
    render(<LeadSalesAgentHistory open lead={lead} onOpenChange={() => undefined} />);
    await user.click((await screen.findAllByRole("button", { name: "View run" }))[0]!);
    expect(
      await screen.findByText("No qualification recorded for this run."),
    ).toBeVisible();
    expect(screen.getByText("No response draft recorded for this run.")).toBeVisible();
    expect(screen.getByText("No email send recorded for this run.")).toBeVisible();
    expect(screen.getByText("No follow-up recorded for this run.")).toBeVisible();
    expect(getLeadQualificationMock).not.toHaveBeenCalled();
    expect(getLeadResponseDraftMock).not.toHaveBeenCalled();
    expect(getLeadFollowUpMock).not.toHaveBeenCalled();
  });

  it("shows run detail loading and error with retry", async () => {
    const user = userEvent.setup();
    const listed = run();
    listLeadSalesRunsMock.mockResolvedValue(page([listed]));
    getSalesRunMock
      .mockRejectedValueOnce(new ApiError("missing", 404))
      .mockResolvedValue({ ...listed, enquiry: "Need a demo" });
    getLeadQualificationMock.mockResolvedValue(qualification());
    getLeadResponseDraftMock.mockResolvedValue(draft({ latest_email_send: null }));
    render(<LeadSalesAgentHistory open lead={lead} onOpenChange={() => undefined} />);
    await user.click((await screen.findAllByRole("button", { name: "View run" }))[0]!);
    expect(
      await screen.findByRole("heading", { name: "Sales run could not be loaded" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Need a demo")).toBeVisible();
    expect(getSalesRunMock).toHaveBeenCalledTimes(2);
  });
});
