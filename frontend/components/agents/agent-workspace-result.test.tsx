import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  AgentWorkspaceResult,
  approvalHandoffHref,
} from "@/components/agents/agent-workspace-result";
import { getApprovals } from "@/lib/api/approvals";
import {
  approveLeadResponseDraft,
  sendLeadResponseDraft,
} from "@/lib/api/leads";
import type { OrchestrationResult } from "@/types/api";

vi.mock("@/lib/api/approvals", () => ({
  getApprovals: vi.fn(),
}));

vi.mock("@/lib/api/leads", () => ({
  approveLeadResponseDraft: vi.fn(),
  sendLeadResponseDraft: vi.fn(),
  rejectLeadResponseDraft: vi.fn(),
}));

function result(
  overrides: Partial<OrchestrationResult> = {},
): OrchestrationResult {
  return {
    execution_id: "exec-1",
    outcome: "SUCCESS",
    execution_status: "COMPLETED",
    plan_id: "plan-1",
    approval_required: false,
    completed_step_count: 1,
    total_step_count: 1,
    stopped_at_step_id: null,
    step_results: [],
    failure_category: null,
    error: null,
    provider: "fake",
    model: "fake-model",
    ...overrides,
  };
}

describe("AgentWorkspaceResult approval handoff", () => {
  it("does not show approval handoff on success", () => {
    render(<AgentWorkspaceResult result={result()} />);
    expect(
      screen.getByRole("heading", { name: "Execution completed" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Review in Approvals" }),
    ).toBeNull();
    expect(approvalHandoffHref(result())).toBeNull();
  });

  it("shows Review in Approvals without Approve/Send and without calling APIs", () => {
    render(
      <AgentWorkspaceResult
        result={result({
          outcome: "APPROVAL_REQUIRED",
          approval_required: true,
          execution_status: "FAILED",
          completed_step_count: 0,
          total_step_count: 1,
          stopped_at_step_id: "s1",
          step_results: [
            {
              step_id: "s1",
              sequence: 0,
              tool_name: "send_response",
              result: {
                call_id: "s1",
                tool_name: "send_response",
                success: false,
                outcome: "APPROVAL_REQUIRED",
                decision: "REQUIRE_APPROVAL",
                risk_level: "HIGH",
                side_effect_level: "SENSITIVE_WRITE",
                output: null,
                error: "requires human approval",
                executed: false,
                failure_category: "POLICY_ERROR",
              },
            },
          ],
        })}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Human approval required" }),
    ).toBeVisible();
    expect(screen.getAllByText("Approval required").length).toBeGreaterThan(0);
    expect(screen.getAllByText("send response").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/No approval was performed automatically/i),
    ).toBeVisible();

    const link = screen.getByRole("link", { name: "Review in Approvals" });
    expect(link).toHaveAttribute("href", "/approvals");

    expect(screen.queryByRole("button", { name: /^approve$/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /^approve$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^send$/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /^send$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /continue/i })).toBeNull();

    expect(getApprovals).not.toHaveBeenCalled();
    expect(approveLeadResponseDraft).not.toHaveBeenCalled();
    expect(sendLeadResponseDraft).not.toHaveBeenCalled();
  });

  it("does not show approval handoff for tool denied", () => {
    render(
      <AgentWorkspaceResult
        result={result({
          outcome: "TOOL_DENIED",
          approval_required: false,
          execution_status: "FAILED",
        })}
      />,
    );
    expect(
      screen.queryByRole("link", { name: "Review in Approvals" }),
    ).toBeNull();
  });

  it("does not show approval handoff for tool failed", () => {
    render(
      <AgentWorkspaceResult
        result={result({
          outcome: "TOOL_FAILED",
          approval_required: false,
          execution_status: "FAILED",
          error: "boom",
        })}
      />,
    );
    expect(
      screen.queryByRole("link", { name: "Review in Approvals" }),
    ).toBeNull();
  });

  it("does not show approval handoff for planner failure", () => {
    render(
      <AgentWorkspaceResult
        result={result({
          outcome: "PLANNING_FAILED",
          approval_required: false,
          execution_status: "FAILED",
          error: "AI provider request failed",
        })}
      />,
    );
    expect(
      screen.queryByRole("link", { name: "Review in Approvals" }),
    ).toBeNull();
  });
});
