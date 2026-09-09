import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ApprovalsPage from "@/app/(app)/approvals/page";
import {
  ApprovalQueue,
  type ApprovalQueueItem,
} from "@/components/approvals/approval-queue";

describe("Approvals page", () => {
  it("renders the page hierarchy and honest unavailable summary", () => {
    render(<ApprovalsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Approvals" }),
    ).toBeVisible();
    for (const section of [
      "Approval summary",
      "Approval workspace",
      "Human control",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: section }),
      ).toBeVisible();
    }

    const metricCards = screen.getAllByRole("article");
    const metricLabels = [
      "Pending",
      "Approved",
      "Rejected",
      "High-risk actions",
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

  it("shows an honest empty approval queue without fabricated requests", () => {
    render(<ApprovalsPage />);

    expect(
      screen.getByRole("heading", { name: "No approval requests" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        /agents begin proposing actions that require human authorization/,
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("list", { name: "Approval queue" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Example approval")).not.toBeInTheDocument();
  });

  it("presents review context with unavailable and disabled decisions", () => {
    render(<ApprovalsPage />);

    expect(
      screen.getByRole("heading", { name: "No approval selected" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Proposed action" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Decision context" }),
    ).toBeVisible();
    for (const label of [
      "What the AI wants to do",
      "Why this was proposed",
      "Proposed by",
      "Relevant context",
      "Risk level",
      "Intended outcome",
    ]) {
      expect(screen.getByText(label)).toBeVisible();
    }
    expect(
      screen.getByRole("button", { name: "Approve action" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Reject action" }),
    ).toBeDisabled();
  });

  it("explains human control and exposes clear risk labels", () => {
    render(<ApprovalsPage />);

    expect(
      screen.getByRole("heading", { name: "People remain in control" }),
    ).toBeVisible();
    const riskLevels = screen.getByLabelText("Available risk levels");
    expect(within(riskLevels).getByText("Low risk")).toBeVisible();
    expect(within(riskLevels).getByText("Medium risk")).toBeVisible();
    expect(within(riskLevels).getByText("High risk")).toBeVisible();
  });

  it("provides clear mobile detail and back navigation", async () => {
    const user = userEvent.setup();
    render(<ApprovalsPage />);

    const queueButton = screen.getByRole("button", {
      name: "Approval queue",
    });
    const detailButton = screen.getByRole("button", { name: "Review detail" });
    const queuePane = document.querySelector("#approval-queue-pane");
    const detailPane = document.querySelector("#approval-detail-pane");

    expect(queueButton).toHaveAttribute("aria-pressed", "true");
    expect(queuePane).toHaveClass("block");
    expect(detailPane).toHaveClass("hidden");

    await user.click(detailButton);
    expect(detailButton).toHaveAttribute("aria-pressed", "true");
    expect(queuePane).toHaveClass("hidden");
    expect(detailPane).toHaveClass("block");

    await user.click(
      screen.getByRole("button", { name: "Back to approval queue" }),
    );
    expect(queueButton).toHaveAttribute("aria-pressed", "true");
    expect(queuePane).toHaveClass("block");
    expect(detailPane).toHaveClass("hidden");
  });

  it("renders keyboard-accessible approval rows when real data is supplied", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const approval: ApprovalQueueItem = {
      id: "approval-1",
      action: "Test action",
      agentName: "Test agent",
      requestedAction: "Test requested action",
      riskLevel: "high",
      requestedTimeLabel: "Test time",
      status: "pending",
    };

    render(
      <ApprovalQueue
        approvals={[approval]}
        selectedId={approval.id}
        onSelect={onSelect}
      />,
    );

    const row = screen.getByRole("button", { name: /Test action/ });
    expect(screen.getByRole("list", { name: "Approval queue" })).toBeVisible();
    expect(row).toHaveAttribute("aria-pressed", "true");
    expect(within(row).getByText("High risk")).toBeVisible();
    expect(within(row).getByText("Pending")).toBeVisible();

    await user.click(row);
    expect(onSelect).toHaveBeenCalledWith(approval);
  });
});
