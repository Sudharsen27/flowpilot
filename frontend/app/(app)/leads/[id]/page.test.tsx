import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LeadWorkspacePage from "@/app/(app)/leads/[id]/page";
import { ApiError } from "@/lib/api/client";
import { getAgents } from "@/lib/api/agents";
import { getInboxConversation } from "@/lib/api/inbox";
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
import type {
  Agent,
  InboxConversationResponse,
  InboxTimelineItem,
  Lead,
  SalesRun,
} from "@/types/api";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "lead-1" }),
}));

vi.mock("@/lib/api/agents", () => ({
  getAgents: vi.fn(),
}));

vi.mock("@/lib/api/inbox", () => ({
  getInboxConversation: vi.fn(),
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
const getInboxConversationMock = vi.mocked(getInboxConversation);

const lead: Lead = {
  id: "lead-1",
  name: "Ada Prospect",
  email: "ada@example.com",
  phone: "+1 555 0100",
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

function emptyConversation(
  overrides: Partial<InboxConversationResponse> = {},
): InboxConversationResponse {
  return {
    lead: {
      lead_id: "lead-1",
      name: "Ada Prospect",
      email: "ada@example.com",
      phone: "+1 555 0100",
      company: "Acme",
      source: "WEBSITE",
      lead_status: "NEW",
      enquiry: null,
      conversation_state: "OPEN",
      needs_approval: false,
      latest_draft: null,
      latest_sales_run: null,
    },
    items: [],
    total_items: 0,
    ...overrides,
  };
}

function timelineItem(
  overrides: Partial<InboxTimelineItem> & Pick<InboxTimelineItem, "id" | "kind">,
): InboxTimelineItem {
  return {
    direction: "internal",
    occurred_at: "2026-09-11T10:00:00Z",
    title: overrides.kind,
    summary: null,
    body: null,
    status: null,
    actor_type: null,
    actor_user_id: null,
    agent_id: null,
    source_entity_type: "LEAD",
    source_entity_id: "lead-1",
    activity_id: null,
    is_draft: false,
    is_sent_message: false,
    ...overrides,
  };
}

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
    getInboxConversationMock.mockReset();
    getLeadMock.mockResolvedValue(lead);
    getAgentsMock.mockResolvedValue([salesAgent]);
    getSalesRunMock.mockResolvedValue(run());
    getInboxConversationMock.mockResolvedValue(emptyConversation());
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

  it("shows loading then the Customer 360 workspace", async () => {
    render(<LeadWorkspacePage />);
    expect(screen.getByText("Loading lead")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { level: 1, name: "Ada Prospect" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Conversation timeline" }),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "AI insights" })).toBeVisible();
    expect(screen.getByText("No Sales Agent activity yet")).toBeVisible();
    expect(
      screen.getByText(/Approval does not send the email/),
    ).toBeVisible();
    expect(screen.getByText("No action required")).toBeVisible();
    expect(await screen.findByText("No conversation activity yet")).toBeVisible();
    expect(screen.queryByText("SECRET ENQUIRY BODY")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Ada Prospect" }),
    ).not.toHaveTextContent("Do not show this enquiry-like note in the header.");
    expect(
      screen.getByText("Do not show this enquiry-like note in the header."),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Open in Inbox" })).toHaveAttribute(
      "href",
      "/inbox?lead=lead-1",
    );
    expect(screen.getByRole("link", { name: "Back to Leads" })).toHaveAttribute(
      "href",
      "/leads",
    );
    await waitFor(() =>
      expect(getInboxConversationMock).toHaveBeenCalledWith("lead-1"),
    );
    expect(screen.getAllByRole("button", { name: "Start Sales Agent" }).length).toBeGreaterThan(
      0,
    );
  });

  it("renders customer profile contact, company, source, and enquiry", async () => {
    getLeadMock.mockResolvedValue({
      ...lead,
      enquiry: "We want a hosted demo",
    });
    render(<LeadWorkspacePage />);
    expect(
      await screen.findByRole("heading", { name: "What they want" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "ada@example.com" })).toHaveAttribute(
      "href",
      "mailto:ada@example.com",
    );
    expect(screen.getByRole("link", { name: "+1 555 0100" })).toHaveAttribute(
      "href",
      "tel:+1 555 0100",
    );
    expect(screen.getAllByText("Acme").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Website").length).toBeGreaterThan(0);
    expect(screen.getAllByText("New").length).toBeGreaterThan(0);
    expect(screen.getByText("We want a hosted demo")).toBeVisible();
    expect(await screen.findByText("Open")).toBeVisible();
  });

  it("shows a 404 when the lead is missing", async () => {
    getLeadMock.mockRejectedValue(new ApiError("missing", 404, { detail: "Not found" }));
    render(<LeadWorkspacePage />);
    expect(await screen.findByText("This lead could not be found.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Back to Leads" })).toHaveAttribute(
      "href",
      "/leads",
    );
    expect(getInboxConversationMock).not.toHaveBeenCalled();
  });

  it("retries after a load error", async () => {
    const user = userEvent.setup();
    getLeadMock
      .mockRejectedValueOnce(new ApiError("down", 500, { detail: "unavailable" }))
      .mockResolvedValue(lead);
    render(<LeadWorkspacePage />);
    expect(await screen.findByText("Unable to load customer")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: "Ada Prospect" }),
    ).toBeVisible();
  });

  it("retries conversation timeline failures independently", async () => {
    const user = userEvent.setup();
    getInboxConversationMock
      .mockRejectedValueOnce(new ApiError("down", 500, { detail: "unavailable" }))
      .mockResolvedValue(
        emptyConversation({
          items: [
            timelineItem({
              id: "evt-1",
              kind: "LEAD_CREATED",
              summary: "Lead captured",
              actor_type: "SYSTEM",
            }),
          ],
          total_items: 1,
        }),
      );
    render(<LeadWorkspacePage />);
    expect(
      await screen.findByText("Unable to load conversation history"),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "AI insights" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Lead created")).toBeVisible();
    expect(
      screen.getByRole("list", { name: "Conversation timeline" }),
    ).toBeVisible();
  });

  it("distinguishes customer, AI draft, sent, and failed timeline events", async () => {
    getInboxConversationMock.mockResolvedValue(
      emptyConversation({
        items: [
          timelineItem({
            id: "evt-1",
            kind: "WEBSITE_ENQUIRY",
            direction: "inbound",
            body: "Please call about pricing.",
            actor_type: "PUBLIC_VISITOR",
          }),
          timelineItem({
            id: "evt-2",
            kind: "DRAFT_GENERATED",
            body: "Thanks for reaching out.",
            is_draft: true,
            actor_type: "AGENT",
            agent_id: "agent-1",
            source_entity_type: "LEAD_RESPONSE_DRAFT",
            source_entity_id: "draft-1",
          }),
          timelineItem({
            id: "evt-3",
            kind: "EMAIL_SENT",
            direction: "outbound",
            body: "Sent reply body",
            is_sent_message: true,
            actor_type: "USER",
            source_entity_type: "LEAD_EMAIL_SEND",
            source_entity_id: "send-1",
          }),
          timelineItem({
            id: "evt-4",
            kind: "EMAIL_FAILED",
            direction: "outbound",
            body: "Failed reply body",
            actor_type: "SYSTEM",
            source_entity_type: "LEAD_EMAIL_SEND",
            source_entity_id: "send-2",
          }),
        ],
        total_items: 4,
      }),
    );
    render(<LeadWorkspacePage />);
    const timeline = await screen.findByRole("list", {
      name: "Conversation timeline",
    });
    expect(within(timeline).getByText("Customer")).toBeVisible();
    expect(within(timeline).getByText("Please call about pricing.")).toBeVisible();
    expect(within(timeline).getByText("AI-generated response")).toBeVisible();
    expect(
      within(timeline).getByText(/Prepared by FlowPilot AI · Not sent to the customer/),
    ).toBeVisible();
    expect(within(timeline).getByText("Sent")).toBeVisible();
    expect(within(timeline).getByText("Failed")).toBeVisible();
    expect(within(timeline).getByText("Needs your review")).toBeVisible();
  });

  it("shows latest Sales Agent status and AI insights without exposing enquiry", async () => {
    getLeadMock.mockResolvedValue({
      ...lead,
      latest_qualification: {
        id: "q-1",
        status: "COMPLETED",
        qualification: "QUALIFIED",
        confidence: 0.91,
        created_at: "2026-09-11T10:00:00Z",
        error: null,
      },
      latest_response_draft: {
        id: "draft-1",
        status: "COMPLETED",
        review_status: "GENERATED",
        created_at: "2026-09-11T10:00:00Z",
      },
      latest_sales_run: {
        id: "run-1",
        agent_id: "agent-1",
        status: "WAITING_APPROVAL",
        stage: "AWAIT_APPROVAL",
        email_send: null,
        follow_up: null,
      },
    });
    getLeadQualificationMock.mockResolvedValue({
      id: "q-1",
      lead_id: "lead-1",
      status: "COMPLETED",
      enquiry: "SECRET ENQUIRY BODY",
      analysis: {
        summary: "Strong buying intent for a demo.",
        intent: "REQUEST_DEMO",
        qualification: "QUALIFIED",
        qualification_reasons: ["Budget mentioned"],
        confidence: 0.91,
        extracted_contact: { name: "Ada", email: "ada@example.com", phone: null },
        extracted_company: { name: "Acme" },
        buying_signals: ["Asked for hosted demo"],
        missing_information: ["Timeline"],
      },
      error: null,
      failure_category: null,
      provider: "fake",
      model: "fake",
      usage: null,
      started_at: "2026-09-11T10:00:00Z",
      completed_at: "2026-09-11T10:00:01Z",
      created_at: "2026-09-11T10:00:00Z",
      duration_ms: 1000,
    });
    getInboxConversationMock.mockResolvedValue(
      emptyConversation({
        lead: {
          lead_id: "lead-1",
          name: "Ada Prospect",
          email: "ada@example.com",
          phone: "+1 555 0100",
          company: "Acme",
          source: "WEBSITE",
          lead_status: "NEW",
          enquiry: null,
          conversation_state: "NEEDS_APPROVAL",
          needs_approval: true,
          latest_draft: {
            id: "draft-1",
            status: "COMPLETED",
            review_status: "GENERATED",
            created_at: "2026-09-11T10:00:00Z",
          },
          latest_sales_run: {
            id: "run-1",
            agent_id: "agent-1",
            status: "WAITING_APPROVAL",
            stage: "AWAIT_APPROVAL",
            email_send: null,
            follow_up: null,
          },
        },
      }),
    );
    render(<LeadWorkspacePage />);
    expect((await screen.findAllByText("Waiting for approval")).length).toBeGreaterThan(0);
    expect(screen.getByText("Inbound qualifier")).toBeVisible();
    expect(screen.getByText("Review AI response")).toBeVisible();
    expect(await screen.findByText("Needs approval")).toBeVisible();
    expect(await screen.findByText("Strong buying intent for a demo.")).toBeVisible();
    expect(screen.getByText("Asked for hosted demo")).toBeVisible();
    expect(screen.getByText("Missing information")).toBeVisible();
    expect(screen.getByText(/Intent:\s*Request demo/)).toBeVisible();
    expect(screen.getByText("Latest AI draft")).toBeVisible();
    expect(screen.getAllByText(/Not sent to the customer/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Start Sales Agent" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Review draft" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Sales Agent history" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Follow-ups" })).toBeVisible();
    expect(screen.queryByText("SECRET ENQUIRY BODY")).not.toBeInTheDocument();
    expect(screen.queryByText("run-1")).not.toBeInTheDocument();
    expect(getLeadQualificationMock).toHaveBeenCalledWith("lead-1", "q-1");
  });

  it("shows follow-up next step from sales run summary", async () => {
    getLeadMock.mockResolvedValue({
      ...lead,
      latest_sales_run: {
        id: "run-1",
        agent_id: "agent-1",
        status: "COMPLETED",
        stage: "DONE",
        email_send: { status: "SENT", completed_at: "2026-09-11T11:00:00Z" },
        follow_up: {
          status: "PENDING",
          due_at: "2026-09-12T10:00:00Z",
          is_overdue: false,
        },
      },
    });
    getSalesRunMock.mockResolvedValue(
      run({
        status: "COMPLETED",
        stage: "DONE",
        response_draft_id: null,
      }),
    );
    render(<LeadWorkspacePage />);
    expect(await screen.findByText("Follow-up scheduled")).toBeVisible();
    expect(screen.getByText("Scheduled")).toBeVisible();
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
    expect(
      screen.getByRole("heading", { level: 1, name: "Ada Prospect" }),
    ).not.toHaveTextContent("We want a hosted demo");
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
