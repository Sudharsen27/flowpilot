import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CommandCenterPage from "@/app/(app)/dashboard/page";
import {
  getAgents,
  listOrganizationExecutions,
  orchestrateAgent,
} from "@/lib/api/agents";
import { getApprovals } from "@/lib/api/approvals";
import { getInbox } from "@/lib/api/inbox";
import { listActivity } from "@/lib/api/activity";
import { getFollowUpOperations, getLeads } from "@/lib/api/leads";
import { listDeals } from "@/lib/api/deals";
import { getPipelineSummary } from "@/lib/api/pipeline";
import { listOrganizationSalesRuns } from "@/lib/api/sales-runs";
import type {
  Deal,
  PipelineSummary,
  Agent,
  ApprovalListResponse,
  FollowUpOperationsResponse,
  LeadListResponse,
} from "@/types/api";

vi.mock("@/lib/api/pipeline", () => ({ getPipelineSummary: vi.fn() }));
vi.mock("@/lib/api/deals", () => ({ listDeals: vi.fn() }));

vi.mock("@/lib/api/activity", () => ({
  listActivity: vi.fn(),
  getActivity: vi.fn(),
}));

vi.mock("@/lib/api/agents", () => ({
  getAgents: vi.fn(),
  listOrganizationExecutions: vi.fn(),
  orchestrateAgent: vi.fn(),
}));

vi.mock("@/lib/api/approvals", () => ({
  getApprovals: vi.fn(),
}));

vi.mock("@/lib/api/inbox", () => ({
  getInbox: vi.fn(),
  getInboxConversation: vi.fn(),
}));

vi.mock("@/lib/api/leads", () => ({
  getLeads: vi.fn(),
  getFollowUpOperations: vi.fn(),
  getLead: vi.fn(),
  getLeadFollowUps: vi.fn(),
  getLeadResponseDraft: vi.fn(),
  generateLeadResponseDraft: vi.fn(),
  updateLeadResponseDraft: vi.fn(),
  approveLeadResponseDraft: vi.fn(),
  rejectLeadResponseDraft: vi.fn(),
  sendLeadResponseDraft: vi.fn(),
}));

vi.mock("@/lib/api/sales-runs", () => ({
  listOrganizationSalesRuns: vi.fn(),
  cancelSalesRun: vi.fn(),
  sendSalesRun: vi.fn(),
}));

const getAgentsMock = vi.mocked(getAgents);
const getApprovalsMock = vi.mocked(getApprovals);
const orchestrateAgentMock = vi.mocked(orchestrateAgent);
const listOrganizationExecutionsMock = vi.mocked(listOrganizationExecutions);
const getInboxMock = vi.mocked(getInbox);
const listActivityMock = vi.mocked(listActivity);
const getLeadsMock = vi.mocked(getLeads);
const getFollowUpOperationsMock = vi.mocked(getFollowUpOperations);
const listOrganizationSalesRunsMock = vi.mocked(listOrganizationSalesRuns);

const agent: Agent = {
  id: "agent-1",
  name: "Inbound qualifier",
  description: "Sales",
  agent_type: "SALES",
  system_instructions: "Be concise.",
  status: "READY",
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-09T10:00:00Z",
};

function leads(total: number, newCount = total): LeadListResponse {
  return {
    items: [],
    limit: 1,
    offset: 0,
    total,
    status_counts: {
      NEW: newCount,
      CONTACTED: 0,
      QUALIFIED: 0,
      UNQUALIFIED: 0,
      CONVERTED: 0,
    },
  };
}

function pendingApprovals(total: number): ApprovalListResponse {
  return { items: [], limit: 1, offset: 0, total };
}

function followUps(overdue: number): FollowUpOperationsResponse {
  return {
    items: [],
    summary: {
      overdue,
      due_today: 0,
      upcoming: 0,
      completed: 0,
      cancelled: 0,
    },
    limit: 20,
    offset: 0,
    total: 0,
  };
}

function pipelineSummary(overrides: Partial<PipelineSummary> = {}): PipelineSummary {
  const stages = ["QUALIFICATION", "DISCOVERY", "PROPOSAL", "NEGOTIATION", "CLOSED_WON", "CLOSED_LOST"] as const;
  const defaults = [10, 25, 50, 75, 100, 0];
  return {
    currency: "INR",
    generated_at: "2026-10-29T10:00:00Z",
    open: { count: 0, total_amount: "0.00", weighted_amount: "0.00" },
    won: { count: 0, total_amount: "0.00" },
    lost: { count: 0, total_amount: "0.00" },
    overdue_open: { count: 0, total_amount: "0.00" },
    by_stage: stages.map((stage, index) => ({
      stage,
      count: 0,
      total_amount: "0.00",
      weighted_amount: "0.00",
      default_probability: defaults[index]!,
    })),
    won_by_month: ["2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01"].map(
      (month) => ({ month, count: 0, total_amount: "0.00" }),
    ),
    excluded_other_currency_count: 0,
    ...overrides,
  };
}

describe("Command Center", () => {
  beforeEach(() => {
    vi.mocked(getPipelineSummary).mockReset();
    vi.mocked(listDeals).mockReset();
    vi.mocked(getPipelineSummary).mockResolvedValue(pipelineSummary());
    vi.mocked(listDeals).mockResolvedValue({ items: [], limit: 5, offset: 0, total: 0 });
    getAgentsMock.mockReset();
    getApprovalsMock.mockReset();
    orchestrateAgentMock.mockReset();
    getInboxMock.mockReset();
    listActivityMock.mockReset();
    getLeadsMock.mockReset();
    getFollowUpOperationsMock.mockReset();
    listOrganizationSalesRunsMock.mockReset();
    listOrganizationExecutionsMock.mockReset();
    getAgentsMock.mockResolvedValue([]);
    listOrganizationExecutionsMock.mockResolvedValue({
      items: [],
      limit: 1,
      offset: 0,
      total: 0,
      status_counts: {
        QUEUED: 0,
        RUNNING: 0,
        COMPLETED: 0,
        FAILED: 0,
        CANCELLED: 0,
      },
    });
    getInboxMock.mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      total: 0,
      state_counts: { OPEN: 0, NEEDS_APPROVAL: 0, CLOSED: 0 },
      needs_approval_count: 0,
      human_attention_count: 0,
    });
    listActivityMock.mockResolvedValue({
      items: [],
      limit: 8,
      offset: 0,
      total: 0,
      type_counts: {
        AI_ACTION: 0,
        APPROVAL: 0,
        HUMAN_ACTION: 0,
        SYSTEM_EVENT: 0,
      },
    });
    getApprovalsMock.mockResolvedValue(pendingApprovals(0));
    getLeadsMock.mockResolvedValue(leads(0));
    getFollowUpOperationsMock.mockResolvedValue(followUps(0));
    listOrganizationSalesRunsMock.mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      total: 0,
      status_counts: {
        RUNNING: 0,
        WAITING_APPROVAL: 0,
        COMPLETED: 0,
        FAILED: 0,
        CANCELLED: 0,
      },
    });
  });

  it("renders the sales workspace and its major sections", async () => {
    render(<CommandCenterPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Dashboard" }),
    ).toBeVisible();
    for (const heading of [
      "Ask FlowPilot",
      "Pipeline at a glance",
      "AI workforce",
      "Needs attention",
      "Failed sends",
      "Overdue follow-ups",
      "Recent activity",
      "Quick actions",
    ]) {
      expect(screen.getByRole("heading", { name: heading })).toBeVisible();
    }
    expect(
      screen.getAllByRole("heading", { name: "Waiting for review" }).length,
    ).toBeGreaterThan(1);
    expect(await screen.findByText("Nothing waiting for review")).toBeVisible();
  });

  it("displays zero leads as 0 and omits unfinished modules from the glance", async () => {
    render(<CommandCenterPage />);
    expect(await screen.findAllByText("0")).not.toHaveLength(0);
    expect(screen.queryByText("Connect a lead source")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Conversation history is not available yet."),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Appointment scheduling is not available yet."),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "No activity yet" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "View all activity" }),
    ).toHaveAttribute("href", "/activity");
    expect(screen.queryByText("Example event")).not.toBeInTheDocument();
    const articles = screen.getAllByRole("article");
    const leadsCard = articles.find((card) =>
      within(card).queryByRole("heading", { name: "Leads" }),
    );
    expect(leadsCard).toBeTruthy();
    expect(within(leadsCard!).getByText("0")).toBeVisible();
  });

  it("recommends creating a lead when the organization has no leads", async () => {
    render(<CommandCenterPage />);

    expect(
      await screen.findByRole("heading", { name: "Start with a lead" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: /Open Leads/ })).toHaveAttribute(
      "href",
      "/leads",
    );
  });

  it("recommends configuring an agent when leads exist without an agent", async () => {
    getLeadsMock.mockResolvedValue(leads(2, 2));
    render(<CommandCenterPage />);

    expect(
      await screen.findByRole("heading", { name: "Configure an AI Agent" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Open AI Agents/ }),
    ).toHaveAttribute("href", "/agents");
  });

  it("recommends qualification when a configured agent and new leads exist", async () => {
    getAgentsMock.mockResolvedValue([agent]);
    getLeadsMock.mockResolvedValue(leads(2, 1));
    render(<CommandCenterPage />);

    expect(
      await screen.findByRole("heading", { name: "Qualify a new lead" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: /Open Leads/ })).toHaveAttribute(
      "href",
      "/leads",
    );
  });

  it("prioritizes approval work as the next action", async () => {
    getLeadsMock.mockResolvedValue(leads(2, 1));
    getApprovalsMock.mockResolvedValue(pendingApprovals(1));
    render(<CommandCenterPage />);

    expect(
      await screen.findByRole("heading", { name: "Your next step" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Review Approvals/ }),
    ).toHaveAttribute("href", "/approvals");
    expect(getApprovalsMock).toHaveBeenCalledWith({
      status: "pending",
      limit: 1,
    });
  });

  it("offers optional website capture and qualification guidance without requiring capture", async () => {
    render(<CommandCenterPage />);

    expect(
      await screen.findByRole("link", { name: "Website enquiries (optional)" }),
    ).toHaveAttribute("href", "/settings");
    expect(
      screen.getByText(
        /create one here or optionally enable website enquiries/i,
      ),
    ).toBeVisible();
  });

  it("shows real agent count instead of not configured copy", async () => {
    getAgentsMock.mockResolvedValue([agent]);
    getLeadsMock.mockResolvedValue(leads(4, 2));
    getFollowUpOperationsMock.mockResolvedValue(followUps(3));
    getApprovalsMock.mockResolvedValue(pendingApprovals(5));
    listOrganizationSalesRunsMock.mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      total: 8,
      status_counts: {
        RUNNING: 0,
        WAITING_APPROVAL: 99,
        COMPLETED: 2,
        FAILED: 1,
        CANCELLED: 0,
      },
    });
    render(<CommandCenterPage />);
    expect(await screen.findByText(/1 configured agent/)).toBeVisible();
    expect(
      screen.getByText(/1 configured agent in this organization.*1 ready/),
    ).toBeVisible();
    expect(screen.queryByText("Not configured")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/No live agent runtime is connected yet/),
    ).not.toBeInTheDocument();
    expect(screen.getByText("5")).toBeVisible();
    expect(screen.queryByText("99")).not.toBeInTheDocument();
    expect(
      screen.getByText("Drafts waiting for a person to review."),
    ).toBeVisible();
    expect(
      screen.queryByText(/2 completed \(email sent\)/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/5 sales runs waiting for approval/),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Completed work is not listed here/)).toBeVisible();
  });

  it("shows recent activity error and retry", async () => {
    listActivityMock.mockRejectedValueOnce(new Error("network"));
    render(<CommandCenterPage />);
    expect(
      await screen.findByRole("heading", {
        name: "Recent activity could not be loaded",
      }),
    ).toBeVisible();
    listActivityMock.mockResolvedValueOnce({
      items: [],
      limit: 8,
      offset: 0,
      total: 0,
      type_counts: {
        AI_ACTION: 0,
        APPROVAL: 0,
        HUMAN_ACTION: 0,
        SYSTEM_EVENT: 0,
      },
    });
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "No activity yet" }),
    ).toBeVisible();
  });

  it("renders live recent activity without fabricated rows", async () => {
    listActivityMock.mockResolvedValue({
      items: [
        {
          id: "event-1",
          type: "AI_ACTION",
          title: "Lead qualified",
          summary: null,
          occurred_at: "2026-09-17T10:00:00Z",
          actor_type: "AGENT",
          actor_user_id: null,
          agent_id: "agent-1",
          entity_type: "LEAD_QUALIFICATION",
          entity_id: "qual-1",
          lead_id: "lead-1",
          status: "COMPLETED",
          sales_run_id: null,
          execution_id: null,
          email_send_id: null,
          follow_up_id: null,
          follow_up_execution_id: null,
          draft_id: null,
          qualification_id: "qual-1",
        },
      ],
      limit: 8,
      offset: 0,
      total: 1,
      type_counts: {
        AI_ACTION: 1,
        APPROVAL: 0,
        HUMAN_ACTION: 0,
        SYSTEM_EVENT: 0,
      },
    });
    render(<CommandCenterPage />);
    expect(await screen.findByText("Lead qualified")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Lead qualified — Open lead" }),
    ).toHaveAttribute("href", "/leads/lead-1");
    expect(
      screen.queryByRole("heading", { name: "No activity yet" }),
    ).not.toBeInTheDocument();
    expect(listActivityMock).toHaveBeenCalledWith({ limit: 8, offset: 0 });
  });

  it("links recent activity to existing destinations and leaves unresolvable events plain", async () => {
    const base = {
      summary: null,
      occurred_at: "2026-09-17T10:00:00Z",
      actor_type: "AGENT" as const,
      actor_user_id: null,
      agent_id: null,
      lead_id: null,
      status: null,
      sales_run_id: null,
      execution_id: null,
      email_send_id: null,
      follow_up_id: null,
      follow_up_execution_id: null,
      draft_id: null,
      qualification_id: null,
    };
    listActivityMock.mockResolvedValue({
      items: [
        {
          ...base,
          id: "event-execution",
          type: "AI_ACTION",
          title: "Agent execution completed",
          entity_type: "AGENT_EXECUTION",
          entity_id: "exec-1",
          execution_id: "exec-1",
          agent_id: "agent-1",
          lead_id: "lead-1",
        },
        {
          ...base,
          id: "event-draft",
          type: "APPROVAL",
          title: "Response draft approved",
          entity_type: "LEAD_RESPONSE_DRAFT",
          entity_id: "draft-1",
          draft_id: "draft-1",
          lead_id: "lead-1",
          status: "APPROVED",
        },
        {
          ...base,
          id: "event-draft-generated",
          type: "AI_ACTION",
          title: "Response draft generated",
          entity_type: "LEAD_RESPONSE_DRAFT",
          entity_id: "draft-2",
          draft_id: "draft-2",
          lead_id: "lead-1",
          status: "GENERATED",
          draft_approval_status: "rejected",
        },
        {
          ...base,
          id: "event-run",
          type: "AI_ACTION",
          title: "Sales Run waiting for approval",
          entity_type: "SALES_RUN",
          entity_id: "run-1",
          sales_run_id: "run-1",
          agent_id: "agent-1",
          lead_id: "lead-1",
        },
        {
          ...base,
          id: "event-knowledge",
          type: "HUMAN_ACTION",
          title: "Knowledge entry updated",
          entity_type: "KNOWLEDGE_ENTRY",
          entity_id: "kb-1",
        },
      ],
      limit: 8,
      offset: 0,
      total: 5,
      type_counts: { AI_ACTION: 3, APPROVAL: 1, HUMAN_ACTION: 1, SYSTEM_EVENT: 0 },
    });
    render(<CommandCenterPage />);

    expect(
      await screen.findByRole("link", {
        name: "Agent execution completed — Open execution",
      }),
    ).toHaveAttribute("href", "/agents/executions?agent_id=agent-1&execution=exec-1");
    expect(
      screen.getByRole("link", { name: "Response draft approved — Open approval" }),
    ).toHaveAttribute("href", "/approvals?status=approved&approval=draft-1");
    // A "generated" event follows the draft to the queue it is in now.
    expect(
      screen.getByRole("link", { name: "Response draft generated — Open approval" }),
    ).toHaveAttribute("href", "/approvals?status=rejected&approval=draft-2");
    expect(
      screen.getByRole("link", { name: "Sales Run waiting for approval — Open sales run" }),
    ).toHaveAttribute("href", "/leads/lead-1?sales_run=run-1&agent=agent-1");
    expect(screen.getByText("Knowledge entry updated")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: /Knowledge entry updated/ }),
    ).not.toBeInTheDocument();
    // Navigation is read-only: approval metrics keep their existing request.
    expect(getApprovalsMock).toHaveBeenCalledWith({ status: "pending", limit: 1 });
  });

  it("runs an instruction on a ready agent and keeps approval in the result", async () => {
    const user = userEvent.setup();
    getAgentsMock.mockResolvedValue([agent]);
    orchestrateAgentMock.mockResolvedValue({
      execution_id: "exec-1",
      outcome: "APPROVAL_REQUIRED",
      execution_status: "COMPLETED",
      plan_id: "plan-1",
      approval_required: true,
      completed_step_count: 1,
      total_step_count: 2,
      stopped_at_step_id: "s2",
      step_results: [],
      failure_category: null,
      error: null,
      provider: "openai",
      model: "test",
    });
    render(<CommandCenterPage />);

    const instruction = await screen.findByPlaceholderText(
      /Qualify today’s new leads/,
    );
    await user.type(instruction, "Qualify the new website lead");
    await user.click(screen.getByRole("button", { name: "Run instruction" }));

    expect(orchestrateAgentMock).toHaveBeenCalledWith("agent-1", {
      instruction: "Qualify the new website lead",
    });
    expect(
      await screen.findByRole("heading", { name: "Human approval required" }),
    ).toBeVisible();
  });

  it("links quick actions only to valid product routes", () => {
    render(<CommandCenterPage />);
    const hrefs = screen
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    for (const href of [
      "/agents",
      "/leads",
      "/deals",
      "/inbox",
      "/approvals",
      "/activity",
    ]) {
      expect(hrefs).toContain(href);
    }
    expect(hrefs).not.toContain("/workflows");
    expect(hrefs.every((href) => href?.startsWith("/"))).toBe(true);
  });

  it("summarizes organization-wide agent runs with filtered links", async () => {
    listOrganizationExecutionsMock.mockResolvedValue({
      items: [],
      limit: 1,
      offset: 0,
      total: 0,
      status_counts: {
        QUEUED: 1,
        RUNNING: 2,
        COMPLETED: 12,
        FAILED: 3,
        CANCELLED: 0,
      },
    });
    render(<CommandCenterPage />);
    const runs = await screen.findByRole("list", {
      name: "Agent runs by status across your organization",
    });
    expect(
      within(runs).getByRole("link", { name: "Failed: 3 agent runs" }),
    ).toHaveAttribute("href", "/agents/executions?status=FAILED");
    expect(
      within(runs).getByRole("link", { name: "Completed: 12 agent runs" }),
    ).toHaveAttribute("href", "/agents/executions?status=COMPLETED");
    expect(
      screen.getByRole("link", { name: "View all agent runs" }),
    ).toHaveAttribute("href", "/agents/executions");
    expect(listOrganizationExecutionsMock).toHaveBeenCalledWith({ limit: 1 });
  });

  it("keeps Command Center metrics when agent run counts fail", async () => {
    listOrganizationExecutionsMock.mockRejectedValue(new Error("network"));
    getAgentsMock.mockResolvedValue([agent]);
    getLeadsMock.mockResolvedValue(leads(5, 2));
    render(<CommandCenterPage />);
    expect(
      await screen.findByText("Agent run counts are unavailable right now."),
    ).toBeVisible();
    expect(
      screen.queryByText("Dashboard metrics could not be loaded."),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText("There are 2 leads with New status."),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "View all agent runs" }),
    ).toHaveAttribute("href", "/agents/executions");
  });

  describe("pipeline dashboard", () => {
    const summary = pipelineSummary({
      open: { count: 3, total_amount: "1250000.50", weighted_amount: "512500.25" },
      won: { count: 2, total_amount: "999999999999.99" },
      overdue_open: { count: 1, total_amount: "250000.00" },
      by_stage: pipelineSummary().by_stage.map((row) =>
        row.stage === "PROPOSAL"
          ? { ...row, count: 2, total_amount: "1000000.50", weighted_amount: "500000.25" }
          : row.stage === "QUALIFICATION"
            ? { ...row, count: 1, total_amount: "250000.00", weighted_amount: "25000.00" }
            : row,
      ),
      won_by_month: pipelineSummary().won_by_month.map((row) =>
        row.month === "2026-10-01" ? { ...row, count: 2, total_amount: "999999999999.99" } : row,
      ),
    });

    function overdueDeal(overrides: Partial<Deal> = {}): Deal {
      return {
        id: "deal-late",
        name: "Late renewal",
        description: null,
        amount: "250000.00",
        currency: "INR",
        stage: "PROPOSAL",
        probability: null,
        effective_probability: 50,
        probability_source: "STAGE_DEFAULT",
        expected_close_date: "2026-09-30",
        closed_at: null,
        owner_user_id: null,
        owner_name: "Olivia Owner",
        lead_id: null,
        lead_name: null,
        lost_reason: null,
        revision: 1,
        stage_entered_at: "2026-09-01T00:00:00Z",
        created_at: "2026-09-01T00:00:00Z",
        updated_at: "2026-09-02T00:00:00Z",
        ...overrides,
      };
    }

    it("shows exact pipeline KPIs and charts from the summary API", async () => {
      vi.mocked(getPipelineSummary).mockResolvedValue(summary);
      render(<CommandCenterPage />);
      expect(await screen.findByLabelText("₹12,50,000.50")).toBeInTheDocument();
      expect(screen.getByText("Weighted ₹5,12,500.25")).toBeInTheDocument();
      expect(screen.getByText("₹9,99,99,99,99,999.99 won to date")).toBeInTheDocument();
      expect(screen.getByText("1 past expected close")).toBeInTheDocument();
      expect(getPipelineSummary).toHaveBeenCalledWith(6);

      const stageTable = screen.getByRole("table", { name: "Open value by stage" });
      expect(within(stageTable).getByRole("rowheader", { name: "Proposal" })).toBeInTheDocument();
      expect(within(stageTable).getByText(/₹10,00,000.50; 2 deals; Weighted ₹5,00,000.25/)).toBeInTheDocument();
      expect(within(stageTable).queryByRole("rowheader", { name: "Closed won" })).not.toBeInTheDocument();
      const months = screen.getByRole("group", { name: "Won revenue by month" });
      expect(
        within(months).getByRole("button", { name: /October 2026, ₹9,99,99,99,99,999.99, 2 deals won/ }),
      ).toBeInTheDocument();
    });

    it("lists open deals past their expected close and links to them", async () => {
      vi.mocked(getPipelineSummary).mockResolvedValue(summary);
      vi.mocked(listDeals).mockImplementation(async (params) =>
        params?.closeDateTo
          ? {
              items: [overdueDeal(), overdueDeal({ id: "deal-won", name: "Closed one", stage: "CLOSED_WON" })],
              limit: 50,
              offset: 0,
              total: 2,
            }
          : { items: [], limit: 5, offset: 0, total: 0 },
      );
      render(<CommandCenterPage />);
      const section = await screen.findByRole("region", { name: "Deals needing attention" });
      expect(await within(section).findByRole("link", { name: "Late renewal" })).toHaveAttribute(
        "href",
        "/deals/deal-late",
      );
      expect(within(section).queryByText("Closed one")).not.toBeInTheDocument();
      expect(
        within(section).getByText("1 open deal is past expected close · ₹2,50,000.00"),
      ).toBeInTheDocument();
    });

    it("keeps the rest of the dashboard when the pipeline summary fails", async () => {
      vi.mocked(getPipelineSummary).mockRejectedValue(new Error("network"));
      getLeadsMock.mockResolvedValue(leads(5, 2));
      render(<CommandCenterPage />);
      expect((await screen.findAllByText("Pipeline figures could not be loaded")).length).toBe(2);
      expect(screen.getAllByText("Deal figures are unavailable.").length).toBeGreaterThan(0);
      expect(await screen.findByText("2 with CRM status New.")).toBeInTheDocument();
      expect(screen.queryByText("Dashboard metrics could not be loaded.")).not.toBeInTheDocument();
    });

    it("offers new-deal and pipeline actions", () => {
      render(<CommandCenterPage />);
      expect(screen.getByRole("link", { name: "New deal" })).toHaveAttribute("href", "/deals?create=1");
      expect(screen.getByRole("link", { name: "Open pipeline" })).toHaveAttribute("href", "/deals/pipeline");
    });
  });
});
