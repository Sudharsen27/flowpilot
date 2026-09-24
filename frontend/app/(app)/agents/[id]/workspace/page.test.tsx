import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentWorkspacePage from "@/app/(app)/agents/[id]/workspace/page";
import { INSTRUCTION_MAX_LENGTH } from "@/components/agents/agent-workspace-panel";
import { ApiError } from "@/lib/api/client";
import { getAgent, orchestrateAgent } from "@/lib/api/agents";
import type { Agent, OrchestrationResult } from "@/types/api";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "agent-real-1" }),
}));

vi.mock("@/lib/api/agents", () => ({
  getAgent: vi.fn(),
  orchestrateAgent: vi.fn(),
}));

const agent: Agent = {
  id: "agent-real-1",
  name: "Inbound qualifier",
  description: "Qualifies new inbound leads.",
  agent_type: "SALES",
  system_instructions: "Be concise.",
  status: "READY",
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-09T10:00:00Z",
};

const getAgentMock = vi.mocked(getAgent);
const orchestrateAgentMock = vi.mocked(orchestrateAgent);

function successResult(
  overrides: Partial<OrchestrationResult> = {},
): OrchestrationResult {
  return {
    execution_id: "exec-1",
    outcome: "SUCCESS",
    execution_status: "COMPLETED",
    plan_id: "plan-1",
    approval_required: false,
    completed_step_count: 2,
    total_step_count: 2,
    stopped_at_step_id: null,
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
          output: { total: 1 },
          error: null,
          executed: true,
          failure_category: null,
        },
      },
      {
        step_id: "s2",
        sequence: 1,
        tool_name: "get_lead",
        result: {
          call_id: "s2",
          tool_name: "get_lead",
          success: true,
          outcome: "SUCCESS",
          decision: "ALLOW",
          risk_level: "LOW",
          side_effect_level: "READ",
          output: {},
          error: null,
          executed: true,
          failure_category: null,
        },
      },
    ],
    failure_category: null,
    error: null,
    provider: "fake",
    model: "fake-model",
    ...overrides,
  };
}

describe("Agent Workspace page", () => {
  beforeEach(() => {
    getAgentMock.mockReset();
    orchestrateAgentMock.mockReset();
    getAgentMock.mockResolvedValue(agent);
  });

  it("renders agent name and instruction input", async () => {
    render(<AgentWorkspacePage />);
    expect(
      await screen.findByRole("heading", { name: "Agent Workspace" }),
    ).toBeVisible();
    expect(screen.getAllByText("Inbound qualifier").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("textbox", { name: /What would you like me to do/i }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Run Agent" })).toBeVisible();
    expect(screen.getByText("SALES")).toBeVisible();
    expect(screen.getByText("Qualifies new inbound leads.")).toBeVisible();
    expect(screen.getByText("0 / 8000")).toBeVisible();
  });

  it("populates examples without executing and clears locally", async () => {
    const user = userEvent.setup();
    render(<AgentWorkspacePage />);
    await screen.findByRole("button", { name: "Run Agent" });

    const example = screen.getByRole("button", {
      name: "Show me the leads that need attention.",
    });
    await user.click(example);
    const input = screen.getByRole("textbox", {
      name: /What would you like me to do/i,
    });
    expect(input).toHaveValue("Show me the leads that need attention.");
    expect(orchestrateAgentMock).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Clear" }));
    expect(input).toHaveValue("");
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
  });

  it("rejects empty instruction without calling the API", async () => {
    const user = userEvent.setup();
    render(<AgentWorkspacePage />);
    await screen.findByRole("button", { name: "Run Agent" });
    expect(screen.getByRole("button", { name: "Run Agent" })).toBeDisabled();
    await user.type(
      screen.getByRole("textbox", { name: /What would you like me to do/i }),
      "   ",
    );
    expect(screen.getByRole("button", { name: "Run Agent" })).toBeDisabled();
    expect(orchestrateAgentMock).not.toHaveBeenCalled();
  });

  it("runs a successful orchestration and shows steps", async () => {
    const user = userEvent.setup();
    orchestrateAgentMock.mockResolvedValue(successResult());
    render(<AgentWorkspacePage />);
    const input = await screen.findByRole("textbox", {
      name: /What would you like me to do/i,
    });
    await user.type(
      input,
      "Find new website leads from today and qualify them.",
    );
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(
      await screen.findByRole("heading", { name: "Execution completed" }),
    ).toBeVisible();
    expect(screen.getByText("2 / 2 completed")).toBeVisible();
    expect(screen.getByText("search leads")).toBeVisible();
    expect(screen.getByText("get lead")).toBeVisible();
    expect(screen.getByText("exec-1")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Review in Approvals" }),
    ).toBeNull();
    expect(orchestrateAgentMock).toHaveBeenCalledWith("agent-real-1", {
      instruction: "Find new website leads from today and qualify them.",
    });
  });

  it("trims instruction before sending", async () => {
    const user = userEvent.setup();
    orchestrateAgentMock.mockResolvedValue(successResult());
    render(<AgentWorkspacePage />);
    await user.type(
      await screen.findByRole("textbox", {
        name: /What would you like me to do/i,
      }),
      "   Find website leads   ",
    );
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    await waitFor(() => {
      expect(orchestrateAgentMock).toHaveBeenCalledWith("agent-real-1", {
        instruction: "Find website leads",
      });
    });
  });

  it("shows approval-required without an Approve action", async () => {
    const user = userEvent.setup();
    orchestrateAgentMock.mockResolvedValue(
      successResult({
        outcome: "APPROVAL_REQUIRED",
        approval_required: true,
        execution_status: "FAILED",
        completed_step_count: 0,
        total_step_count: 2,
        stopped_at_step_id: "s1",
        step_results: [
          {
            step_id: "s1",
            sequence: 0,
            tool_name: "draft_note",
            result: {
              call_id: "s1",
              tool_name: "draft_note",
              success: false,
              outcome: "APPROVAL_REQUIRED",
              decision: "REQUIRE_APPROVAL",
              risk_level: "MEDIUM",
              side_effect_level: "READ",
              output: null,
              error: "requires human approval",
              executed: false,
              failure_category: "POLICY_ERROR",
            },
          },
        ],
        error: "Tool 'draft_note' requires human approval",
      }),
    );
    render(<AgentWorkspacePage />);
    await user.type(
      await screen.findByRole("textbox", {
        name: /What would you like me to do/i,
      }),
      "Draft a note",
    );
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(
      await screen.findByRole("heading", { name: "Human approval required" }),
    ).toBeVisible();
    expect(
      screen.getByText(/No approval was performed automatically/i),
    ).toBeVisible();
    expect(screen.getAllByText("draft note").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Approval required").length).toBeGreaterThan(0);
    const reviewLink = screen.getByRole("link", {
      name: "Review in Approvals",
    });
    expect(reviewLink).toHaveAttribute("href", "/approvals");
    expect(screen.queryByRole("button", { name: /approve/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^send$/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /^approve$/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /^send$/i })).toBeNull();
    expect(screen.queryByRole("link", { name: "Review draft" })).toBeNull();
  });

  it("deep-links Review draft when create_response_draft returns draft_id", async () => {
    const user = userEvent.setup();
    orchestrateAgentMock.mockResolvedValue(
      successResult({
        outcome: "SUCCESS",
        approval_required: false,
        completed_step_count: 1,
        total_step_count: 1,
        step_results: [
          {
            step_id: "s1",
            sequence: 0,
            tool_name: "create_response_draft",
            result: {
              call_id: "s1",
              tool_name: "create_response_draft",
              success: true,
              outcome: "SUCCESS",
              decision: "ALLOW",
              risk_level: "LOW",
              side_effect_level: "WRITE",
              output: {
                draft_id: "draft-from-orch",
                lead_id: "lead-9",
                status: "COMPLETED",
                review_status: "GENERATED",
                revision: 1,
                created_at: "2026-09-22T10:00:00Z",
              },
              error: null,
              executed: true,
              failure_category: null,
            },
          },
        ],
      }),
    );
    render(<AgentWorkspacePage />);
    await user.type(
      await screen.findByRole("textbox", {
        name: /What would you like me to do/i,
      }),
      "Draft a reply for this lead",
    );
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(
      await screen.findByRole("heading", { name: "Execution completed" }),
    ).toBeVisible();
    expect(screen.getByText("Draft created")).toBeVisible();
    const reviewLink = screen.getByRole("link", { name: "Review draft" });
    expect(reviewLink).toHaveAttribute(
      "href",
      "/approvals?approval=draft-from-orch",
    );
    expect(reviewLink.getAttribute("href")).not.toContain("exec-1");
    expect(screen.queryByRole("button", { name: /^approve$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^send$/i })).toBeNull();
  });

  it("shows tool denied state without approval handoff", async () => {
    const user = userEvent.setup();
    orchestrateAgentMock.mockResolvedValue(
      successResult({
        outcome: "TOOL_DENIED",
        approval_required: false,
        execution_status: "FAILED",
        completed_step_count: 0,
        total_step_count: 1,
        step_results: [],
        error: "Tool 'echo' is denied by policy",
      }),
    );
    render(<AgentWorkspacePage />);
    await user.type(
      await screen.findByRole("textbox", {
        name: /What would you like me to do/i,
      }),
      "Echo something",
    );
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(
      await screen.findByRole("heading", { name: "Tool denied by policy" }),
    ).toBeVisible();
    expect(screen.getByText("Tool 'echo' is denied by policy")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Review in Approvals" }),
    ).toBeNull();
  });

  it("shows tool failed state without approval handoff", async () => {
    const user = userEvent.setup();
    orchestrateAgentMock.mockResolvedValue(
      successResult({
        outcome: "TOOL_FAILED",
        approval_required: false,
        execution_status: "FAILED",
        completed_step_count: 0,
        total_step_count: 1,
        error: "boom",
        step_results: [],
      }),
    );
    render(<AgentWorkspacePage />);
    await user.type(
      await screen.findByRole("textbox", {
        name: /What would you like me to do/i,
      }),
      "Do a thing",
    );
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(
      await screen.findByRole("heading", { name: "A tool step failed" }),
    ).toBeVisible();
    expect(screen.getByText("boom")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Review in Approvals" }),
    ).toBeNull();
  });

  it("shows planner failure state without approval handoff", async () => {
    const user = userEvent.setup();
    orchestrateAgentMock.mockResolvedValue(
      successResult({
        outcome: "PLANNING_FAILED",
        approval_required: false,
        execution_status: "FAILED",
        completed_step_count: 0,
        total_step_count: 0,
        step_results: [],
        error: "AI provider request failed",
      }),
    );
    render(<AgentWorkspacePage />);
    await user.type(
      await screen.findByRole("textbox", {
        name: /What would you like me to do/i,
      }),
      "Plan this",
    );
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(
      await screen.findByRole("heading", { name: "Agent planning failed" }),
    ).toBeVisible();
    expect(screen.getByText("AI provider request failed")).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Review in Approvals" }),
    ).toBeNull();
  });

  it("shows network error and allows another submission", async () => {
    const user = userEvent.setup();
    orchestrateAgentMock.mockRejectedValueOnce(new Error("network"));
    orchestrateAgentMock.mockResolvedValueOnce(successResult());
    render(<AgentWorkspacePage />);
    const input = await screen.findByRole("textbox", {
      name: /What would you like me to do/i,
    });
    await user.type(input, "Try once");
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(
      await screen.findByText("Something went wrong while running the agent."),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(
      await screen.findByRole("heading", { name: "Execution completed" }),
    ).toBeVisible();
  });

  it("moves focus to an orchestration error and can run again", async () => {
    const user = userEvent.setup();
    orchestrateAgentMock.mockRejectedValueOnce(new Error("network"));
    orchestrateAgentMock.mockResolvedValueOnce(successResult());
    render(<AgentWorkspacePage />);
    const input = await screen.findByRole("textbox", {
      name: /What would you like me to do/i,
    });
    await user.type(input, "Try this again");
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    const error = await screen.findByText(
      "Something went wrong while running the agent.",
    );
    expect(document.activeElement).toBe(error);
    await user.click(screen.getByRole("button", { name: "Run again" }));
    expect(
      await screen.findByRole("heading", { name: "Execution completed" }),
    ).toBeVisible();
    expect(orchestrateAgentMock).toHaveBeenCalledTimes(2);
  });

  it("disables submit while running", async () => {
    const user = userEvent.setup();
    let resolveRun: ((value: OrchestrationResult) => void) | undefined;
    orchestrateAgentMock.mockReturnValue(
      new Promise((resolve) => {
        resolveRun = resolve;
      }),
    );
    render(<AgentWorkspacePage />);
    await user.type(
      await screen.findByRole("textbox", {
        name: /What would you like me to do/i,
      }),
      "Slow run",
    );
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    expect(await screen.findByRole("button", { name: "Running…" })).toBeDisabled();
    expect(screen.getByText("Running your instruction…")).toBeVisible();
    expect(orchestrateAgentMock).toHaveBeenCalledTimes(1);
    resolveRun?.(successResult());
    expect(
      await screen.findByRole("heading", { name: "Execution completed" }),
    ).toBeVisible();
  });

  it("sends only instruction in the API payload", async () => {
    const user = userEvent.setup();
    orchestrateAgentMock.mockResolvedValue(successResult());
    render(<AgentWorkspacePage />);
    await user.type(
      await screen.findByRole("textbox", {
        name: /What would you like me to do/i,
      }),
      "Only instruction",
    );
    await user.click(screen.getByRole("button", { name: "Run Agent" }));
    await waitFor(() => expect(orchestrateAgentMock).toHaveBeenCalled());
    expect(orchestrateAgentMock.mock.calls[0]?.[1]).toEqual({
      instruction: "Only instruction",
    });
    expect(orchestrateAgentMock.mock.calls[0]?.[1]).not.toHaveProperty(
      "organization_id",
    );
    expect(orchestrateAgentMock.mock.calls[0]?.[1]).not.toHaveProperty("role");
    expect(orchestrateAgentMock.mock.calls[0]?.[1]).not.toHaveProperty(
      "user_id",
    );
  });

  it("enforces the maximum instruction length", async () => {
    const user = userEvent.setup();
    render(<AgentWorkspacePage />);
    const input = await screen.findByRole("textbox", {
      name: /What would you like me to do/i,
    });
    await user.click(input);
    await user.paste("x".repeat(INSTRUCTION_MAX_LENGTH + 1));
    expect(screen.getByRole("button", { name: "Run Agent" })).toBeDisabled();
    expect(orchestrateAgentMock).not.toHaveBeenCalled();
  });

  it("shows agent not found", async () => {
    getAgentMock.mockRejectedValue(new ApiError("missing", 404, {}));
    render(<AgentWorkspacePage />);
    expect(
      await screen.findByRole("heading", { level: 1, name: "Agent not found" }),
    ).toBeVisible();
  });
});
