import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  AgentWorkspaceResult,
  approvalHandoffHref,
  extractCreatedDraft,
  resolveApprovalHandoff,
} from "@/components/agents/agent-workspace-result";
import { getApprovals } from "@/lib/api/approvals";
import {
  approveLeadResponseDraft,
  sendLeadResponseDraft,
} from "@/lib/api/leads";
import { buildApprovalsHref } from "@/lib/approvals-url";
import type { OrchestrationResult, PlanStepResult } from "@/types/api";

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

function draftStep(
  draftId: string,
  overrides: Partial<PlanStepResult> = {},
): PlanStepResult {
  return {
    step_id: "draft-step",
    sequence: 0,
    tool_name: "create_response_draft",
    result: {
      call_id: "draft-step",
      tool_name: "create_response_draft",
      success: true,
      outcome: "SUCCESS",
      decision: "ALLOW",
      risk_level: "LOW",
      side_effect_level: "WRITE",
      output: {
        draft_id: draftId,
        lead_id: "lead-1",
        status: "COMPLETED",
        review_status: "GENERATED",
        revision: 1,
        created_at: "2026-09-22T10:00:00Z",
      },
      error: null,
      executed: true,
      failure_category: null,
    },
    ...overrides,
  };
}

describe("AgentWorkspaceResult draft handoff", () => {
  it("does not show approval handoff on plain success", () => {
    render(<AgentWorkspaceResult result={result()} />);
    expect(
      screen.getByRole("heading", { name: "Execution completed" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Review in Approvals" }),
    ).toBeNull();
    expect(screen.queryByRole("link", { name: "Review draft" })).toBeNull();
    expect(approvalHandoffHref(result())).toBeNull();
  });

  it("shows Review draft deep-link for create_response_draft output", () => {
    const payload = result({
      step_results: [draftStep("draft-real-99")],
    });
    render(<AgentWorkspaceResult result={payload} />);

    expect(screen.getByText("Draft created")).toBeVisible();
    expect(
      screen.getAllByText(/Review required before sending/i).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("draft-real-99")).toBeVisible();
    expect(screen.getByText("lead-1")).toBeVisible();
    expect(screen.getByText("GENERATED")).toBeVisible();

    const link = screen.getByRole("link", { name: "Review draft" });
    expect(link).toHaveAttribute(
      "href",
      buildApprovalsHref({ approvalId: "draft-real-99" }),
    );
    expect(link).toHaveAttribute("href", "/approvals?approval=draft-real-99");

    expect(screen.queryByRole("button", { name: /^approve$/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /^approve$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^send$/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /^send$/i })).toBeNull();
    expect(getApprovals).not.toHaveBeenCalled();
    expect(approveLeadResponseDraft).not.toHaveBeenCalled();
    expect(sendLeadResponseDraft).not.toHaveBeenCalled();
  });

  it("never treats execution_id as draft_id", () => {
    const payload = result({
      execution_id: "exec-looks-like-draft",
      step_results: [
        {
          step_id: "s1",
          sequence: 0,
          tool_name: "search_leads",
          result: {
            call_id: "s1",
            tool_name: "search_leads",
            success: true,
            outcome: "SUCCESS",
            decision: "ALLOW",
            risk_level: "LOW",
            side_effect_level: "READ",
            output: {
              draft_id: "should-ignore-from-other-tool",
              total: 1,
            },
            error: null,
            executed: true,
            failure_category: null,
          },
        },
      ],
    });
    expect(extractCreatedDraft(payload)).toBeNull();
    expect(resolveApprovalHandoff(payload)).toBeNull();
    render(<AgentWorkspaceResult result={payload} />);
    expect(screen.queryByRole("link", { name: "Review draft" })).toBeNull();
    expect(
      screen.queryByRole("link", { name: "Review in Approvals" }),
    ).toBeNull();
  });

  it("ignores failed create_response_draft without inventing a link", () => {
    const payload = result({
      outcome: "TOOL_FAILED",
      approval_required: false,
      execution_status: "FAILED",
      step_results: [
        {
          step_id: "s1",
          sequence: 0,
          tool_name: "create_response_draft",
          result: {
            call_id: "s1",
            tool_name: "create_response_draft",
            success: false,
            outcome: "FAILURE",
            decision: "ALLOW",
            risk_level: "LOW",
            side_effect_level: "WRITE",
            output: { draft_id: "draft-should-not-use" },
            error: "boom",
            executed: true,
            failure_category: "TOOL_ERROR",
          },
        },
      ],
    });
    expect(extractCreatedDraft(payload)).toBeNull();
    render(<AgentWorkspaceResult result={payload} />);
    expect(screen.queryByRole("link", { name: "Review draft" })).toBeNull();
  });

  it("keeps generic Review in Approvals when approval_required and no draft_id", () => {
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

    const link = screen.getByRole("link", { name: "Review in Approvals" });
    expect(link).toHaveAttribute("href", "/approvals");
    expect(screen.queryByRole("link", { name: "Review draft" })).toBeNull();
    expect(screen.queryByRole("button", { name: /^approve$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^send$/i })).toBeNull();
  });

  it("prefers draft deep-link over generic fallback when both present", () => {
    const payload = result({
      approval_required: true,
      step_results: [draftStep("draft-preferred")],
    });
    const handoff = resolveApprovalHandoff(payload);
    expect(handoff?.label).toBe("Review draft");
    expect(handoff?.href).toBe("/approvals?approval=draft-preferred");
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
    expect(screen.queryByRole("link", { name: "Review draft" })).toBeNull();
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
