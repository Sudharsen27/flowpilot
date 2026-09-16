import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LeadWorkspacePage from "@/app/(app)/leads/[id]/page";
import { ApiError } from "@/lib/api/client";
import { getAgents } from "@/lib/api/agents";
import {
  getLead,
  getLeadFollowUps,
  getLeadQualification,
  getLeadResponseDraft,
  getLeadFollowUp,
} from "@/lib/api/leads";
import {
  getSalesRun,
  listLeadSalesRuns,
  startLeadSalesRun,
} from "@/lib/api/sales-runs";
import type { Agent, Lead, SalesRun } from "@/types/api";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "lead-1" }),
}));

vi.mock("@/lib/api/agents", () => ({
  getAgents: vi.fn(),
}));

vi.mock("@/lib/api/leads", () => ({
  getLead: vi.fn(),
  updateLead: vi.fn(),
  getLeadFollowUps: vi.fn(),
  getLeadFollowUp: vi.fn(),
  getLeadQualification: vi.fn(),
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

vi.mock("@/lib/api/sales-runs", () => ({
  getSalesRun: vi.fn(),
  listLeadSalesRuns: vi.fn(),
  startLeadSalesRun: vi.fn(),
}));

const getLeadMock = vi.mocked(getLead);
const getAgentsMock = vi.mocked(getAgents);
const getSalesRunMock = vi.mocked(getSalesRun);
const startLeadSalesRunMock = vi.mocked(startLeadSalesRun);
const listLeadSalesRunsMock = vi.mocked(listLeadSalesRuns);
const getLeadFollowUpsMock = vi.mocked(getLeadFollowUps);
const getLeadResponseDraftMock = vi.mocked(getLeadResponseDraft);
const getLeadQualificationMock = vi.mocked(getLeadQualification);
const getLeadFollowUpMock = vi.mocked(getLeadFollowUp);

const lead: Lead = {
  id: "lead-1",
  name: "Ada Prospect",
  email: "ada@example.com",
  phone: null,
  company: "Acme",
  source: "WEBSITE",
  status: "NEW",
  notes: "Do not show this enquiry-like note in the header.",
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-10T10:00:00Z",
};

const salesAgent: Agent = {
  id: "agent-1",
  name: "Inbound qualifier",
  description: "Sales",
  agent_type: "SALES",
  system_instructions: "Be concise.",
  status: "READY",
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-09T10:00:00Z",
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

describe("Lead workspace", () => {
  beforeEach(() => {
    getLeadMock.mockReset();
    getAgentsMock.mockReset();
    getSalesRunMock.mockReset();
    startLeadSalesRunMock.mockReset();
    listLeadSalesRunsMock.mockReset();
    getLeadFollowUpsMock.mockReset();
    getLeadResponseDraftMock.mockReset();
    getLeadQualificationMock.mockReset();
    getLeadFollowUpMock.mockReset();
    getLeadMock.mockResolvedValue(lead);
    getAgentsMock.mockResolvedValue([salesAgent]);
    getSalesRunMock.mockResolvedValue(run());
    listLeadSalesRunsMock.mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      total: 0,
    });
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
  });

  it("shows loading then the empty Sales Agent workspace", async () => {
    render(<LeadWorkspacePage />);
    expect(screen.getByText("Loading lead")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Ada Prospect" })).toBeVisible();
    expect(screen.getByText("No Sales Agent work yet")).toBeVisible();
    expect(
      screen.getByText(/Approval does not send the email/),
    ).toBeVisible();
    expect(screen.queryByText("SECRET ENQUIRY BODY")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Do not show this enquiry-like note in the header."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/conversation/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/activity feed/i)).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Start Sales Agent" }).length).toBeGreaterThan(
      0,
    );
  });

  it("shows a 404 when the lead is missing", async () => {
    getLeadMock.mockRejectedValue(new ApiError("missing", 404, { detail: "Not found" }));
    render(<LeadWorkspacePage />);
    expect(await screen.findByText("This lead could not be found.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Back to Leads" })).toHaveAttribute(
      "href",
      "/leads",
    );
  });

  it("retries after a load error", async () => {
    const user = userEvent.setup();
    getLeadMock
      .mockRejectedValueOnce(new ApiError("down", 500, { detail: "unavailable" }))
      .mockResolvedValue(lead);
    render(<LeadWorkspacePage />);
    expect(await screen.findByText("This lead could not be loaded.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("heading", { name: "Ada Prospect" })).toBeVisible();
  });

  it("shows latest Sales Agent status without exposing enquiry", async () => {
    getLeadMock.mockResolvedValue({
      ...lead,
      latest_sales_run: {
        id: "run-1",
        agent_id: "agent-1",
        status: "WAITING_APPROVAL",
        stage: "AWAIT_APPROVAL",
        email_send: null,
        follow_up: null,
      },
    });
    render(<LeadWorkspacePage />);
    expect((await screen.findAllByText("Waiting for approval")).length).toBeGreaterThan(0);
    expect(screen.getByText("Inbound qualifier")).toBeVisible();
    expect(screen.getByRole("button", { name: "Start Sales Agent" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Review draft" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Sales Agent history" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Follow-ups" })).toBeVisible();
    expect(screen.queryByText("SECRET ENQUIRY BODY")).not.toBeInTheDocument();
    expect(screen.queryByText("run-1")).not.toBeInTheDocument();
  });

  it("starts a sales run with enquiry and agent_id only", async () => {
    const user = userEvent.setup();
    startLeadSalesRunMock.mockResolvedValue(run());
    getLeadMock
      .mockResolvedValueOnce(lead)
      .mockResolvedValue({
        ...lead,
        latest_sales_run: {
          id: "run-1",
          agent_id: "agent-1",
          status: "WAITING_APPROVAL",
          stage: "AWAIT_APPROVAL",
          email_send: null,
          follow_up: null,
        },
      });
    render(<LeadWorkspacePage />);
    await user.click(
      (await screen.findAllByRole("button", { name: "Start Sales Agent" }))[0]!,
    );
    expect(await screen.findByRole("heading", { name: "Start Sales Agent" })).toBeVisible();
    const submit = screen.getByRole("button", { name: "Start" });
    await user.click(submit);
    expect(screen.getByText("Enquiry is required.")).toBeVisible();
    await user.type(screen.getByLabelText(/Enquiry/), "Need a demo next week");
    await user.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() =>
      expect(startLeadSalesRunMock).toHaveBeenCalledWith("lead-1", {
        enquiry: "Need a demo next week",
        agent_id: "agent-1",
      }),
    );
    const payload = startLeadSalesRunMock.mock.calls[0]?.[1];
    expect(payload).not.toHaveProperty("lead_id");
    expect(payload).not.toHaveProperty("organization_id");
    expect(await screen.findAllByText("Waiting for approval")).not.toHaveLength(0);
  });

  it("shows the stored enquiry and prefills Start Sales Agent", async () => {
    const user = userEvent.setup();
    getLeadMock.mockResolvedValue({
      ...lead,
      enquiry: "We want a hosted demo",
    });
    startLeadSalesRunMock.mockResolvedValue(run());
    render(<LeadWorkspacePage />);
    expect(await screen.findAllByText("We want a hosted demo")).not.toHaveLength(0);
    expect(screen.getByRole("heading", { name: "Ada Prospect" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Ada Prospect" })).not.toHaveTextContent(
      "We want a hosted demo",
    );
    await user.click(screen.getAllByRole("button", { name: "Start Sales Agent" })[0]!);
    expect(await screen.findByRole("heading", { name: "Start Sales Agent" })).toBeVisible();
    expect(screen.getByLabelText(/Enquiry/)).toHaveValue("We want a hosted demo");
    expect(screen.queryByText("lead-1")).not.toBeInTheDocument();
  });

  it("keeps a 409 open-run error in the dialog", async () => {
    const user = userEvent.setup();
    startLeadSalesRunMock.mockRejectedValue(
      new ApiError("Conflict", 409, {
        detail: "This lead already has an open sales run. Cancel it or wait for review before starting another.",
      }),
    );
    render(<LeadWorkspacePage />);
    await user.click(
      (await screen.findAllByRole("button", { name: "Start Sales Agent" }))[0]!,
    );
    await user.type(await screen.findByLabelText(/Enquiry/), "Need a demo");
    await user.click(screen.getByRole("button", { name: "Start" }));
    expect(
      await screen.findByText(/This lead already has an open sales run/),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Start Sales Agent" })).toBeVisible();
  });

  it("shows an unavailable state when no Sales Agent is ready", async () => {
    getAgentsMock.mockResolvedValue([
      { ...salesAgent, status: "DRAFT" },
      {
        ...salesAgent,
        id: "support-1",
        name: "Support",
        agent_type: "SUPPORT",
        status: "READY",
      },
    ]);
    render(<LeadWorkspacePage />);
    expect(await screen.findByText("No Sales Agent is ready")).toBeVisible();
    expect(screen.getByRole("link", { name: "Open AI Agents" })).toHaveAttribute(
      "href",
      "/agents",
    );
  });
});
