import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentsPage from "@/app/(app)/agents/page";
import { getAgents } from "@/lib/api/agents";
import type { Agent } from "@/types/api";

vi.mock("@/lib/api/agents", () => ({
  getAgents: vi.fn(),
}));

const agent: Agent = {
  id: "agent-real-1",
  name: "Inbound qualifier",
  description: "Qualifies new inbound leads.",
  agent_type: "SALES",
  system_instructions: "Ask concise qualification questions.",
  status: "ACTIVE",
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-09T10:00:00Z",
};

const getAgentsMock = vi.mocked(getAgents);

describe("AI Agents page", () => {
  beforeEach(() => {
    getAgentsMock.mockReset();
  });

  it("shows a loading state before the API responds", () => {
    getAgentsMock.mockReturnValue(new Promise(() => undefined));
    render(<AgentsPage />);
    expect(screen.getByText("Loading agents")).toBeVisible();
  });

  it("shows the real empty state without fake configured agents", async () => {
    getAgentsMock.mockResolvedValue([]);
    render(<AgentsPage />);
    expect(
      await screen.findByRole("heading", { name: "No agents configured" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("list", { name: "Configured agents" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Test agent")).not.toBeInTheDocument();
  });

  it("renders real API fields and links to the real id", async () => {
    getAgentsMock.mockResolvedValue([agent]);
    render(<AgentsPage />);
    const grid = await screen.findByRole("list", {
      name: "Configured agents",
    });
    expect(within(grid).getByText("Qualifies new inbound leads.")).toBeVisible();
    expect(within(grid).getByText("Sales")).toBeVisible();
    expect(within(grid).getByText("Active")).toBeVisible();
    expect(
      within(grid).getByRole("link", { name: "Inbound qualifier" }),
    ).toHaveAttribute("href", "/agents/agent-real-1");
    expect(screen.getByText("Sep 9, 2026")).toBeVisible();
    expect(screen.queryByText(/execution count/i)).not.toBeInTheDocument();
  });

  it("sends status and type filters to the API", async () => {
    const user = userEvent.setup();
    getAgentsMock.mockResolvedValue([agent]);
    render(<AgentsPage />);
    await screen.findByText("Inbound qualifier");

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Agent status" }),
      "ACTIVE",
    );
    await waitFor(() =>
      expect(getAgentsMock).toHaveBeenLastCalledWith({
        status: "ACTIVE",
        agentType: undefined,
      }),
    );

    await user.selectOptions(
      screen.getByRole("combobox", { name: "Agent type" }),
      "SALES",
    );
    await waitFor(() =>
      expect(getAgentsMock).toHaveBeenLastCalledWith({
        status: "ACTIVE",
        agentType: "SALES",
      }),
    );
  });

  it("searches only within the fetched list", async () => {
    const user = userEvent.setup();
    getAgentsMock.mockResolvedValue([agent]);
    render(<AgentsPage />);
    await screen.findByText("Inbound qualifier");
    await user.type(
      screen.getByRole("searchbox", { name: "Search loaded agents" }),
      "support",
    );
    expect(
      screen.getByRole("heading", { name: "No loaded agents match" }),
    ).toBeVisible();
    expect(screen.getByText(/applied locally/)).toBeVisible();
  });

  it("shows an API error and retries", async () => {
    const user = userEvent.setup();
    getAgentsMock
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce([agent]);
    render(<AgentsPage />);
    expect(
      await screen.findByRole("heading", {
        name: "Agents could not be loaded",
      }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Inbound qualifier")).toBeVisible();
    expect(getAgentsMock).toHaveBeenCalledTimes(2);
  });

  it("derives honest configuration counts from loaded agents", async () => {
    getAgentsMock.mockResolvedValue([
      agent,
      { ...agent, id: "draft", name: "Draft agent", status: "DRAFT" },
    ]);
    render(<AgentsPage />);
    await screen.findByText("Inbound qualifier");
    const cards = screen.getAllByRole("article").slice(0, 4);
    expect(within(cards[0]).getByText("2")).toBeVisible();
    expect(within(cards[1]).getByText("1")).toBeVisible();
    expect(within(cards[2]).getByText("0")).toBeVisible();
    expect(within(cards[3]).getByText("1")).toBeVisible();
  });
});
