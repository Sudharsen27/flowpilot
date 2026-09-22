import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { AgentCard } from "@/components/agents/agent-card";

const agent = {
  id: "sales-groq-verify-id",
  name: "Sales Groq Verify",
  description: "Verifies Groq-backed sales flows.",
  agentType: "Sales",
  status: "active" as const,
  configurationState: "Configured",
  updatedAt: "Sep 9, 2026",
};

describe("AgentCard", () => {
  it("renders configured agent fields", () => {
    render(<AgentCard agent={agent} />);
    expect(
      screen.getByRole("heading", { name: "Sales Groq Verify" }),
    ).toBeVisible();
    expect(screen.getByText("Verifies Groq-backed sales flows.")).toBeVisible();
    expect(screen.getByText("Sales")).toBeVisible();
    expect(screen.getByText("Configured")).toBeVisible();
    expect(screen.getByText("Sep 9, 2026")).toBeVisible();
    expect(screen.getByText("View agent →")).toBeVisible();
  });

  it("links the whole card to the agent detail route using agent.id", () => {
    render(<AgentCard agent={agent} />);
    const link = screen.getByRole("link", { name: "Sales Groq Verify" });
    expect(link).toHaveAttribute("href", "/agents/sales-groq-verify-id");
  });

  it("encodes special characters in the agent id", () => {
    render(
      <AgentCard
        agent={{
          ...agent,
          id: "agent/with space",
          name: "Encoded agent",
        }}
      />,
    );
    expect(
      screen.getByRole("link", { name: "Encoded agent" }),
    ).toHaveAttribute("href", "/agents/agent%2Fwith%20space");
  });

  it("is keyboard focusable as a link", async () => {
    const user = userEvent.setup();
    render(<AgentCard agent={agent} />);
    await user.tab();
    expect(screen.getByRole("link", { name: "Sales Groq Verify" })).toHaveFocus();
  });
});
