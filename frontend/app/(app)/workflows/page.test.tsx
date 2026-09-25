import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import WorkflowsPage from "@/app/(app)/workflows/page";
import {
  WorkflowList,
  type WorkflowListItem,
} from "@/components/workflows/workflow-list";
import { WorkflowStatusBadge } from "@/components/workflows/workflow-status-badge";

describe("Workflows page", () => {
  it("renders the page hierarchy and honest unavailable overview", () => {
    render(<WorkflowsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Workflows" }),
    ).toBeVisible();
    for (const section of [
      "Workflow overview",
      "Configured workflows",
      "Workflow blueprint",
      "Configuration concepts",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: section }),
      ).toBeVisible();
    }

    const metricCards = screen.getAllByRole("article");
    const metricLabels = [
      "Total workflows",
      "Active",
      "Draft",
      "Needs attention",
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

  it("keeps workflow creation honestly unavailable", () => {
    render(<WorkflowsPage />);

    const createButton = screen.getByRole("button", {
      name: "Create workflow",
    });
    expect(createButton).toBeDisabled();
    expect(createButton).toHaveAccessibleDescription(
      "Workflow creation is planned and is not available yet.",
    );
  });

  it("shows an honest setup state without fabricated workflows", () => {
    render(<WorkflowsPage />);

    expect(
      screen.getByRole("heading", { name: "No workflows configured" }),
    ).toBeVisible();
    expect(
      screen.getAllByText(/Workflow creation is planned and is not available yet/),
    ).not.toHaveLength(0);
    expect(
      screen.getByRole("link", { name: /Review AI Agents/ }),
    ).toHaveAttribute("href", "/agents");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("Test workflow")).not.toBeInTheDocument();
  });

  it("renders the conceptual workflow and planned agent connection", () => {
    render(<WorkflowsPage />);

    const steps = screen.getByRole("list", {
      name: "Conceptual workflow steps",
    });
    expect(within(steps).getAllByRole("listitem")).toHaveLength(6);
    for (const step of [
      "Trigger",
      "AI agent / action",
      "Condition",
      "Approval",
      "Action",
      "Outcome",
    ]) {
      expect(within(steps).getByRole("button", { name: new RegExp(step) })).toBeVisible();
    }
    expect(screen.getByText("Blueprint only")).toBeVisible();
    expect(
      screen.getByLabelText("Planned agent workflow example"),
    ).toBeVisible();
    expect(screen.getByText("Configuration concept")).toBeVisible();
  });

  it("labels trigger and action catalogs as non-functional concepts", () => {
    render(<WorkflowsPage />);

    const triggers = screen.getByRole("list", {
      name: "Available trigger concepts",
    });
    const actions = screen.getByRole("list", {
      name: "Available action concepts",
    });

    expect(within(triggers).getByText("New customer enquiry")).toBeVisible();
    expect(within(triggers).getByText("External webhook")).toBeVisible();
    expect(within(actions).getByText("Qualify lead")).toBeVisible();
    expect(within(actions).getByText("Request human approval")).toBeVisible();
    expect(screen.getAllByText("Planned")).toHaveLength(13);
    expect(screen.getByText("Execution unavailable")).toBeVisible();
  });

  it("maps all planned workflow statuses to clear labels", () => {
    render(
      <>
        <WorkflowStatusBadge status="draft" />
        <WorkflowStatusBadge status="active" />
        <WorkflowStatusBadge status="paused" />
        <WorkflowStatusBadge status="needs-attention" />
      </>,
    );

    for (const label of ["Draft", "Active", "Paused", "Needs attention"]) {
      expect(screen.getByText(label)).toBeVisible();
    }
  });

  it("selects blueprint steps and reveals related workspaces", async () => {
    const user = userEvent.setup();
    render(<WorkflowsPage />);

    const steps = screen.getByRole("list", {
      name: "Conceptual workflow steps",
    });
    const trigger = within(steps).getByRole("button", { name: /Trigger/ });
    const approval = within(steps).getByRole("button", { name: /Approval/ });

    expect(trigger).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("heading", { name: "Trigger" })).toBeVisible();

    await user.click(approval);
    expect(approval).toHaveAttribute("aria-pressed", "true");
    expect(trigger).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("heading", { name: "Approval" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Open Approvals" })).toHaveAttribute(
      "href",
      "/approvals",
    );
    await waitFor(() =>
      expect(screen.getByRole("region", { name: "Approval" })).toHaveFocus(),
    );
  });

  it("supports keyboard selection and keeps the detail region focused", async () => {
    const user = userEvent.setup();
    render(<WorkflowsPage />);

    const condition = screen.getByRole("button", { name: /Condition/ });
    condition.focus();
    await user.keyboard("{Enter}");

    expect(condition).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("heading", { name: "Condition" })).toBeVisible();
    await waitFor(() =>
      expect(screen.getByRole("region", { name: "Condition" })).toHaveFocus(),
    );
  });

  it("supports desktop table and mobile list representations for real rows", () => {
    const workflow: WorkflowListItem = {
      id: "workflow-1",
      name: "Test workflow",
      description: "Test workflow description",
      trigger: "Test trigger",
      status: "draft",
    };

    render(<WorkflowList workflows={[workflow]} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByText("Test workflow")).toHaveLength(2);
    expect(screen.getAllByText("Draft")).toHaveLength(2);
    expect(screen.getAllByText("Not connected")).toHaveLength(2);
  });
});
