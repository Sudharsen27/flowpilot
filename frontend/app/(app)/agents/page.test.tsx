import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AgentsPage from "@/app/(app)/agents/page";
import { AgentGrid } from "@/components/agents/agent-grid";
import { AgentStatusBadge } from "@/components/agents/agent-status-badge";

describe("AI Agents page", () => {
  it("renders the page hierarchy and honest unavailable overview", () => {
    render(<AgentsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "AI Agents" }),
    ).toBeVisible();
    for (const section of [
      "Agent overview",
      "Configured agents",
      "Agent blueprints",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: section }),
      ).toBeVisible();
    }

    const metricCards = screen.getAllByRole("article").slice(0, 4);
    const metricLabels = [
      "Total agents",
      "Active",
      "Needs attention",
      "Draft or configuring",
    ];
    expect(metricCards).toHaveLength(metricLabels.length);
    metricLabels.forEach((label, index) => {
      expect(
        within(metricCards[index]).getByRole("heading", {
          level: 3,
          name: label,
        }),
      ).toBeVisible();
    });
    expect(screen.getAllByText("—")).toHaveLength(4);
  });

  it("keeps agent creation visibly unavailable", () => {
    render(<AgentsPage />);

    const createButton = screen.getByRole("button", { name: "Create agent" });
    expect(createButton).toBeDisabled();
    expect(createButton).toHaveAccessibleDescription(
      "Agent creation is not available yet.",
    );
  });

  it("shows an honest setup state and valid related workspace links", () => {
    render(<AgentsPage />);

    expect(
      screen.getByRole("heading", { name: "No agents configured" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        /after agent configuration and persistence are implemented/,
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("list", { name: "Configured agents" }),
    ).not.toBeInTheDocument();

    const relatedWorkspaces = screen.getByRole("navigation", {
      name: "Explore related workspaces",
    });
    for (const [label, href] of [
      ["Leads", "/leads"],
      ["AI Inbox", "/inbox"],
      ["Approvals", "/approvals"],
      ["Workflows", "/workflows"],
    ]) {
      expect(
        within(relatedWorkspaces).getByRole("link", { name: label }),
      ).toHaveAttribute("href", href);
    }
    expect(screen.queryByText("Test agent")).not.toBeInTheDocument();
  });

  it("labels planned agent types and capabilities as blueprint concepts", () => {
    render(<AgentsPage />);

    const blueprints = screen.getByRole("list", {
      name: "Planned agent blueprints",
    });
    for (const agentType of [
      "Sales Agent",
      "Support Agent",
      "Operations Agent",
      "Communication Agent",
    ]) {
      expect(
        within(blueprints).getByRole("heading", { name: agentType }),
      ).toBeVisible();
    }
    expect(within(blueprints).getAllByText("Blueprint only")).toHaveLength(4);
    expect(within(blueprints).getByText("Qualify leads")).toBeVisible();
    expect(within(blueprints).getByText("Respond to customers")).toBeVisible();
    expect(
      within(blueprints).getByText("Create or update records"),
    ).toBeVisible();
    expect(within(blueprints).getByText("Request human review")).toBeVisible();
  });

  it("maps all planned agent statuses to clear text labels", () => {
    render(
      <>
        <AgentStatusBadge status="draft" />
        <AgentStatusBadge status="ready" />
        <AgentStatusBadge status="active" />
        <AgentStatusBadge status="paused" />
        <AgentStatusBadge status="needs-attention" />
      </>,
    );

    for (const label of [
      "Draft",
      "Ready",
      "Active",
      "Paused",
      "Needs attention",
    ]) {
      expect(screen.getByText(label)).toBeVisible();
    }
  });

  it("renders a semantic responsive grid when real agent data is supplied", () => {
    render(
      <AgentGrid
        agents={[
          {
            id: "agent-1",
            name: "Test agent",
            purpose: "Test purpose",
            status: "draft",
            capabilities: ["Test capability"],
            configurationState: "Test configuration",
          },
        ]}
      />,
    );

    const grid = screen.getByRole("list", { name: "Configured agents" });
    expect(grid).toHaveClass("sm:grid-cols-2", "xl:grid-cols-3");
    expect(
      within(grid).getByRole("heading", { name: "Test agent" }),
    ).toBeVisible();
    expect(within(grid).getByText("Test capability")).toBeVisible();
    expect(within(grid).getByText("Unavailable")).toBeVisible();
  });
});
