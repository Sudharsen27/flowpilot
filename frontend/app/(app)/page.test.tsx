import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CommandCenterPage from "@/app/(app)/page";
import { getAgents } from "@/lib/api/agents";
import { getFollowUpOperations, getLeads } from "@/lib/api/leads";
import { listOrganizationSalesRuns } from "@/lib/api/sales-runs";
import type { Agent, FollowUpOperationsResponse, LeadListResponse } from "@/types/api";

vi.mock("@/lib/api/agents", () => ({
  getAgents: vi.fn(),
}));

vi.mock("@/lib/api/leads", () => ({
  getLeads: vi.fn(),
  getFollowUpOperations: vi.fn(),
}));

vi.mock("@/lib/api/sales-runs", () => ({
  listOrganizationSalesRuns: vi.fn(),
}));

const getAgentsMock = vi.mocked(getAgents);
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
    limit: 1,
    offset: 0,
    total: 0,
  };
}

describe("Command Center", () => {
  beforeEach(() => {
    getAgentsMock.mockReset();
    getLeadsMock.mockReset();
    getFollowUpOperationsMock.mockReset();
    listOrganizationSalesRunsMock.mockReset();
    getAgentsMock.mockResolvedValue([]);
    getLeadsMock.mockResolvedValue(leads(0));
    getFollowUpOperationsMock.mockResolvedValue(followUps(0));
    listOrganizationSalesRunsMock.mockResolvedValue({
      items: [],
      limit: 1,
      offset: 0,
      total: 0,
    });
  });

  it("renders the dashboard and its major sections", async () => {
    render(<CommandCenterPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Command Center" }),
    ).toBeVisible();
    for (const heading of [
      "Business overview",
      "AI workforce",
      "Needs attention",
      "Recent activity",
      "Quick actions",
    ]) {
      expect(screen.getByRole("heading", { name: heading })).toBeVisible();
    }
    expect(await screen.findAllByText("0")).not.toHaveLength(0);
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
      screen.getByText(/organization-wide activity feed is not available yet/),
    ).toBeVisible();
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
      limit: 1,
      offset: 0,
      total: 5,
    });
    render(<CommandCenterPage />);
    expect(await screen.findByText("1 agent")).toBeVisible();
    expect(screen.getByText(/1 agent in this organization, 1 ready/)).toBeVisible();
    expect(screen.queryByText("Not configured")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/No live agent runtime is connected yet/),
    ).not.toBeInTheDocument();
    expect(screen.getByText("5")).toBeVisible();
    expect(screen.getByText("3 follow-ups overdue.")).toBeVisible();
    expect(screen.getByText(/5 sales runs waiting for approval/)).toBeVisible();
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
    ]) {
      expect(hrefs).toContain(href);
    }
    expect(hrefs.every((href) => href?.startsWith("/"))).toBe(true);
  });
});
