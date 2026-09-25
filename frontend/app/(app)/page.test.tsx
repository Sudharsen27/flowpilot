import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CommandCenterPage from "@/app/(app)/page";
import { getAgents } from "@/lib/api/agents";
import { listActivity } from "@/lib/api/activity";
import { getFollowUpOperations, getLeads } from "@/lib/api/leads";
import { listOrganizationSalesRuns } from "@/lib/api/sales-runs";
import type { Agent, FollowUpOperationsResponse, LeadListResponse } from "@/types/api";

vi.mock("@/lib/api/activity", () => ({
  listActivity: vi.fn(),
  getActivity: vi.fn(),
}));

vi.mock("@/lib/api/agents", () => ({
  getAgents: vi.fn(),
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

describe("Command Center", () => {
  beforeEach(() => {
    getAgentsMock.mockReset();
    listActivityMock.mockReset();
    getLeadsMock.mockReset();
    getFollowUpOperationsMock.mockReset();
    listOrganizationSalesRunsMock.mockReset();
    getAgentsMock.mockResolvedValue([]);
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
      screen.getByRole("heading", { level: 1, name: "Command Center" }),
    ).toBeVisible();
    for (const heading of [
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

  it("displays zero leads as 0 and keeps conversations and appointments unavailable", async () => {
    render(<CommandCenterPage />);
    expect(await screen.findAllByText("0")).not.toHaveLength(0);
    expect(screen.queryByText("Connect a lead source")).not.toBeInTheDocument();
    expect(
      screen.getByText("Conversation history is not available yet."),
    ).toBeVisible();
    expect(
      screen.getByText("Appointment scheduling is not available yet."),
    ).toBeVisible();
    expect(
      await screen.findByRole("heading", { name: "No activity yet" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "View all activity" })).toHaveAttribute(
      "href",
      "/activity",
    );
    expect(screen.queryByText("Example event")).not.toBeInTheDocument();
    const articles = screen.getAllByRole("article");
    const conversations = articles.find((card) =>
      within(card).queryByRole("heading", { name: "Conversations" }),
    );
    expect(conversations).toBeTruthy();
    expect(within(conversations!).getByText("—")).toBeVisible();
  });

  it("shows real agent count instead of not configured copy", async () => {
    getAgentsMock.mockResolvedValue([agent]);
    getLeadsMock.mockResolvedValue(leads(4, 2));
    getFollowUpOperationsMock.mockResolvedValue(followUps(3));
    listOrganizationSalesRunsMock.mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      total: 8,
      status_counts: {
        RUNNING: 0,
        WAITING_APPROVAL: 5,
        COMPLETED: 2,
        FAILED: 1,
        CANCELLED: 0,
      },
    });
    render(<CommandCenterPage />);
    expect(await screen.findByText(/1 configured agent/)).toBeVisible();
    expect(screen.getByText(/1 configured agent in this organization.*1 ready/)).toBeVisible();
    expect(screen.queryByText("Not configured")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/No live agent runtime is connected yet/),
    ).not.toBeInTheDocument();
    expect(screen.getByText("5")).toBeVisible();
    expect(screen.getByText("Sales runs with a draft ready for review.")).toBeVisible();
    expect(screen.queryByText(/2 completed \(email sent\)/)).not.toBeInTheDocument();
    expect(screen.queryByText(/5 sales runs waiting for approval/)).not.toBeInTheDocument();
    expect(
      screen.getByText(/Completed work is not listed here/),
    ).toBeVisible();
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
    expect(await screen.findByRole("heading", { name: "No activity yet" })).toBeVisible();
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
    expect(screen.queryByRole("heading", { name: "No activity yet" })).not.toBeInTheDocument();
    expect(listActivityMock).toHaveBeenCalledWith({ limit: 8, offset: 0 });
  });

  it("links quick actions only to valid product routes", () => {
    render(<CommandCenterPage />);
    const hrefs = screen
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));
    for (const href of [
      "/agents",
      "/leads",
      "/inbox",
      "/approvals",
      "/workflows",
      "/activity",
    ]) {
      expect(hrefs).toContain(href);
    }
    expect(hrefs.every((href) => href?.startsWith("/"))).toBe(true);
  });
});
