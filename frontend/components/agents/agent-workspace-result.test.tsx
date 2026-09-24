import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
  let writeText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
  });

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
    expect(screen.getByText("Revision").parentElement).toHaveTextContent("1");

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

  it("copies real execution and draft IDs with temporary confirmation", async () => {
    const user = userEvent.setup();
    writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const payload = result({ step_results: [draftStep("draft-copy-1")] });
    render(<AgentWorkspaceResult result={payload} />);

    await user.click(screen.getByRole("button", { name: "Copy execution ID" }));
    expect(writeText).toHaveBeenCalledWith("exec-1");
    expect(
      await screen.findByRole("button", { name: "execution ID copied" }),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Copy draft ID" }));
    expect(writeText).toHaveBeenCalledWith("draft-copy-1");
    expect(
      await screen.findByRole("button", { name: "draft ID copied" }),
    ).toBeVisible();
  });

  it("shows optional provider and model only when returned", () => {
    const { rerender } = render(
      <AgentWorkspaceResult
        result={result({ provider: "Groq", model: "GPT-OSS 20B" })}
      />,
    );
    expect(screen.getByText("Groq")).toBeVisible();
    expect(screen.getByText("GPT-OSS 20B")).toBeVisible();

    rerender(<AgentWorkspaceResult result={result({ provider: null, model: null })} />);
    expect(screen.queryByText("Provider")).toBeNull();
    expect(screen.queryByText("Model")).toBeNull();
  });

  it("shows returned step metadata and safely expandable output", async () => {
    const user = userEvent.setup();
    render(
      <AgentWorkspaceResult
        result={
          result({
            step_results: [
              {
                step_id: "step-read",
                sequence: 2,
                tool_name: "search_leads",
                result: {
                  call_id: "step-read",
                  tool_name: "search_leads",
                  success: true,
                  outcome: "SUCCESS",
                  decision: "ALLOW",
                  risk_level: "LOW",
                  side_effect_level: "READ",
                  output: {
                    total: 3,
                    organization_id: "internal-org",
                  },
                  error: null,
                  executed: true,
                  failure_category: null,
                },
              },
              {
                step_id: "step-approval",
                sequence: 3,
                tool_name: "protected_action",
                result: {
                  call_id: "step-approval",
                  tool_name: "protected_action",
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
          })
        }
      />,
    );

    expect(screen.getByText("READ")).toBeVisible();
    expect(screen.getByText("Risk LOW")).toBeVisible();
    expect(screen.getByText("ALLOW")).toBeVisible();
    expect(screen.getAllByText("Approval required").length).toBeGreaterThan(1);
    expect(screen.getByText("Risk HIGH")).toBeVisible();
    expect(screen.getByText("SENSITIVE_WRITE")).toBeVisible();
    expect(screen.getByText("Not executed")).toBeVisible();

    await user.click(screen.getByText("View output"));
    expect(screen.getByText(/"total": 3/)).toBeVisible();
    expect(screen.queryByText("internal-org")).toBeNull();
  });

  it("focuses the result heading and offers retry without approval controls", async () => {
    const onRunAgain = vi.fn();
    const user = userEvent.setup();
    render(
      <AgentWorkspaceResult
        result={
          result({
            outcome: "TOOL_FAILED",
            execution_status: "FAILED",
            error: "Tool failed safely",
          })
        }
        onRunAgain={onRunAgain}
      />,
    );
    const heading = screen.getByRole("heading", { name: "A tool step failed" });
    expect(document.activeElement).toBe(heading);
    await user.click(screen.getByRole("button", { name: "Run again" }));
    expect(onRunAgain).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: /^Approve$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Reject$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Send response$/i })).toBeNull();
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
