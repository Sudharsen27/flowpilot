import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AgentDetailPage from "@/app/(app)/agents/[id]/page";

describe("Agent Detail page", () => {
  it("renders a neutral configuration route with back navigation", () => {
    render(<AgentDetailPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Agent configuration",
      }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "AI Agents" })).toHaveAttribute(
      "href",
      "/agents",
    );
    expect(
      screen.getByRole("heading", {
        name: "Configuration is not connected",
      }),
    ).toBeVisible();
    expect(
      screen.getByText(/No agent record is loaded, changes are not tracked/),
    ).toBeVisible();
  });

  it("renders all configuration sections with a clear heading hierarchy", () => {
    render(<AgentDetailPage />);

    for (const heading of [
      "Agent identity",
      "Instructions",
      "Capabilities",
      "Tools",
      "Knowledge",
      "Human approval and safety",
      "Communication behavior",
      "Configuration status",
      "Test agent",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: heading }),
      ).toBeVisible();
    }
  });

  it("provides labeled, disabled identity and instruction controls", () => {
    render(<AgentDetailPage />);

    expect(screen.getByRole("textbox", { name: "Agent name" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "Agent type" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "Description" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "Purpose" })).toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: "Agent instructions" }),
    ).toBeDisabled();
    expect(screen.getByText(/this editor does not save changes/)).toBeVisible();
  });

  it("renders disabled capability concepts without executing them", () => {
    render(<AgentDetailPage />);

    for (const capability of [
      "Understand enquiries",
      "Qualify leads",
      "Respond to customers",
      "Create or update records",
      "Schedule follow-ups",
      "Escalate to humans",
    ]) {
      const checkbox = screen.getByRole("checkbox", { name: capability });
      expect(checkbox).toBeDisabled();
      expect(checkbox).not.toBeChecked();
    }
    expect(screen.getByText(/does not execute any action/)).toBeVisible();
  });

  it("shows tools and knowledge as unconnected setup concepts", () => {
    render(<AgentDetailPage />);

    expect(screen.getByText("No tools connected")).toBeVisible();
    expect(screen.getByText("No knowledge connected")).toBeVisible();
    expect(
      screen.getByRole("list", { name: "Tool connection concepts" }),
    ).toBeVisible();
    expect(
      screen.getByRole("list", { name: "Knowledge source concepts" }),
    ).toBeVisible();
    expect(screen.getAllByText("Not connected")).toHaveLength(10);
  });

  it("renders disabled human-control and communication settings", () => {
    render(<AgentDetailPage />);

    for (const policy of [
      "Require approval for sensitive actions",
      "Escalate uncertain conversations",
      "Allow automatic customer responses",
      "Require approval before external actions",
    ]) {
      const control = screen.getByRole("switch", { name: policy });
      expect(control).toBeDisabled();
      expect(control).toHaveAttribute("aria-checked", "false");
    }

    for (const setting of [
      "Tone",
      "Response style",
      "Business-hours behavior",
      "Human-handoff behavior",
    ]) {
      expect(screen.getByRole("combobox", { name: setting })).toBeDisabled();
    }
  });

  it("keeps save, activation, and runtime behavior honestly unavailable", () => {
    render(<AgentDetailPage />);

    const saveButtons = screen.getAllByRole("button", {
      name: "Save configuration",
    });
    expect(saveButtons).toHaveLength(2);
    saveButtons.forEach((button) => expect(button).toBeDisabled());
    expect(saveButtons[0]).toHaveAccessibleDescription(
      "Saving is unavailable because agent persistence is not implemented.",
    );
    expect(
      screen.getByRole("button", { name: "Open test preview" }),
    ).toBeDisabled();
    expect(screen.getByText("Runtime unavailable")).toBeVisible();
    expect(screen.getByText("Not tracked")).toBeVisible();
    expect(screen.getByText("Not ready")).toBeVisible();
    expect(screen.queryByText("Sales Agent")).not.toBeInTheDocument();
  });

  it("uses an adaptive content and status layout", () => {
    const { container } = render(<AgentDetailPage />);

    const responsiveLayout = container.querySelector(
      '[data-slot="agent-detail-layout"]',
    );
    expect(responsiveLayout).toBeInTheDocument();
    expect(responsiveLayout).toHaveClass(
      "grid",
      "xl:grid-cols-[minmax(0,1fr)_20rem]",
    );
    expect(
      screen.getByRole("complementary", { name: "Configuration status" }),
    ).toBeInTheDocument();
  });
});
