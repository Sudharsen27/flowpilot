import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AgentDetailPage from "@/app/(app)/agents/[id]/page";
import { ApiError } from "@/lib/api/client";
import {
  activateAgent,
  cancelAgentExecution,
  createAgentExecution,
  getAgent,
  getAgentExecution,
  listAgentExecutions,
  listToolInvocations,
  markAgentReady,
  pauseAgent,
  runAgentExecution,
  updateAgent,
} from "@/lib/api/agents";
import {
  cancelSalesRun,
  listSalesRuns,
} from "@/lib/api/sales-runs";
import type {
  Agent,
  AgentExecutionCreated,
  AgentExecutionDetail,
  AgentExecutionListItem,
  AgentExecutionResult,
  ToolInvocationListItem,
} from "@/types/api";

const authMock = vi.hoisted(() => ({
  role: "OWNER" as "OWNER" | "ADMIN" | "MEMBER",
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "agent-real-1" }),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    session: { membership: { role: authMock.role } },
    isLoading: false,
  }),
}));

vi.mock("@/lib/api/agents", () => ({
  getAgent: vi.fn(),
  updateAgent: vi.fn(),
  markAgentReady: vi.fn(),
  activateAgent: vi.fn(),
  pauseAgent: vi.fn(),
  createAgentExecution: vi.fn(),
  runAgentExecution: vi.fn(),
  cancelAgentExecution: vi.fn(),
  listAgentExecutions: vi.fn(),
  getAgentExecution: vi.fn(),
  listToolInvocations: vi.fn(),
}));

vi.mock("@/lib/api/sales-runs", () => ({
  listSalesRuns: vi.fn(),
  startSalesRun: vi.fn(),
  cancelSalesRun: vi.fn(),
  getSalesRun: vi.fn(),
}));

vi.mock("@/lib/api/leads", () => ({
  getLead: vi.fn(),
}));

const agent: Agent = {
  id: "agent-real-1",
  name: "Inbound qualifier",
  description: "Qualifies new inbound leads.",
  agent_type: "SALES",
  system_instructions: "Ask concise qualification questions.",
  status: "READY",
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-09T10:00:00Z",
};

const getAgentMock = vi.mocked(getAgent);
const updateAgentMock = vi.mocked(updateAgent);
const markAgentReadyMock = vi.mocked(markAgentReady);
const activateAgentMock = vi.mocked(activateAgent);
const pauseAgentMock = vi.mocked(pauseAgent);
const createAgentExecutionMock = vi.mocked(createAgentExecution);
const runAgentExecutionMock = vi.mocked(runAgentExecution);
const cancelAgentExecutionMock = vi.mocked(cancelAgentExecution);
const listAgentExecutionsMock = vi.mocked(listAgentExecutions);
const getAgentExecutionMock = vi.mocked(getAgentExecution);
const listToolInvocationsMock = vi.mocked(listToolInvocations);
const listSalesRunsMock = vi.mocked(listSalesRuns);
const cancelSalesRunMock = vi.mocked(cancelSalesRun);

const emptyHistory = {
  items: [] as AgentExecutionListItem[],
  limit: 20,
  offset: 0,
  total: 0,
};

function historyItem(
  id: string,
  overrides: Partial<AgentExecutionListItem> = {},
): AgentExecutionListItem {
  return {
    id,
    status: "COMPLETED",
    provider: "openai",
    model: "gpt-4o-mini",
    started_at: "2026-09-09T10:00:00Z",
    completed_at: "2026-09-09T10:00:02Z",
    created_at: "2026-09-09T10:00:00Z",
    input_preview: "Preview of the run",
    error_preview: null,
    duration_ms: 2000,
    failure_category: null,
    ...overrides,
  };
}

const executionResult: AgentExecutionResult = {
  execution_id: "exec-real-1",
  status: "COMPLETED",
  output: "This lead is qualified.",
  provider: "openai",
  model: "gpt-4.1-mini",
  usage: { total_tokens: 42 },
  error: null,
};

const startedExecution: AgentExecutionCreated = {
  execution_id: "exec-real-1",
  status: "RUNNING",
  started_at: "2026-09-09T10:00:00Z",
};

function mockStartedRun(
  result: AgentExecutionResult | Promise<AgentExecutionResult> = executionResult,
) {
  createAgentExecutionMock.mockResolvedValue(startedExecution);
  if (result instanceof Promise) {
    runAgentExecutionMock.mockReturnValue(result);
  } else {
    runAgentExecutionMock.mockResolvedValue(result);
  }
}

describe("Agent Detail page", () => {
  beforeEach(() => {
    getAgentMock.mockReset();
    updateAgentMock.mockReset();
    markAgentReadyMock.mockReset();
    activateAgentMock.mockReset();
    pauseAgentMock.mockReset();
    createAgentExecutionMock.mockReset();
    runAgentExecutionMock.mockReset();
    cancelAgentExecutionMock.mockReset();
    listAgentExecutionsMock.mockReset();
    getAgentExecutionMock.mockReset();
    listToolInvocationsMock.mockReset();
    listSalesRunsMock.mockReset();
    cancelSalesRunMock.mockReset();
    listAgentExecutionsMock.mockResolvedValue(emptyHistory);
    listToolInvocationsMock.mockResolvedValue({
      items: [],
      limit: 50,
      offset: 0,
      total: 0,
    });
    listSalesRunsMock.mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      total: 0,
    });
    authMock.role = "OWNER";
  });

  it("shows loading while requesting the agent id", () => {
    getAgentMock.mockReturnValue(new Promise(() => undefined));
    render(<AgentDetailPage />);
    expect(screen.getByText("Loading agent details")).toBeVisible();
    expect(getAgentMock).toHaveBeenCalledWith("agent-real-1");
  });

  it("renders real identity, status, and system instructions", async () => {
    getAgentMock.mockResolvedValue(agent);
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Inbound qualifier",
      }),
    ).toBeVisible();
    expect(screen.getByText("Qualifies new inbound leads.")).toBeVisible();
    expect(screen.getAllByText("Ready").length).toBeGreaterThan(0);
    expect(screen.getByRole("textbox", { name: "Agent name" })).toHaveValue(
      "Inbound qualifier",
    );
    expect(screen.getByRole("combobox", { name: "Agent type" })).toHaveValue(
      "SALES",
    );
    expect(
      screen.getByRole("textbox", { name: "Agent instructions" }),
    ).toHaveValue("Ask concise qualification questions.");
    expect(
      screen.getByRole("textbox", { name: "Agent instructions" }),
    ).toBeEnabled();
    screen
      .getAllByRole("button", { name: "Save configuration" })
      .forEach((button) => expect(button).toBeDisabled());
  });

  it("shows a not-found state with back navigation", async () => {
    getAgentMock.mockRejectedValue(new ApiError("Request failed: 404", 404));
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("heading", { level: 1, name: "Agent not found" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Back to AI Agents" }),
    ).toHaveAttribute("href", "/agents");
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("shows a retryable API error and retries", async () => {
    const user = userEvent.setup();
    getAgentMock
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(agent);
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("heading", {
        name: "Agent could not be loaded",
      }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Inbound qualifier",
      }),
    ).toBeVisible();
    expect(getAgentMock).toHaveBeenCalledTimes(2);
  });

  it("keeps the existing back breadcrumb", async () => {
    getAgentMock.mockResolvedValue(agent);
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("link", { name: "AI Agents" }),
    ).toHaveAttribute("href", "/agents");
  });

  it.each(["OWNER", "ADMIN"] as const)(
    "allows %s to edit and sends only changed fields",
    async (role) => {
      const user = userEvent.setup();
      authMock.role = role;
      getAgentMock.mockResolvedValue(agent);
      updateAgentMock.mockResolvedValue({
        ...agent,
        name: "Updated qualifier",
      });
      render(<AgentDetailPage />);
      const name = await screen.findByRole("textbox", { name: "Agent name" });
      expect(
        screen.getAllByRole("button", { name: "Save configuration" })[0],
      ).toBeDisabled();
      await user.clear(name);
      await user.type(name, "Updated qualifier");
      const saveButtons = screen.getAllByRole("button", {
        name: "Save configuration",
      });
      expect(saveButtons[0]).toBeEnabled();
      await user.click(saveButtons[0]);
      expect(updateAgentMock).toHaveBeenCalledWith("agent-real-1", {
        name: "Updated qualifier",
      });
      expect(await screen.findByRole("status")).toHaveTextContent(
        "Configuration saved.",
      );
      expect(
        screen.getByRole("textbox", { name: "Agent name" }),
      ).toHaveValue("Updated qualifier");
      expect(
        screen.getAllByRole("button", { name: "Save configuration" })[0],
      ).toBeDisabled();
    },
  );

  it("shows a save error and preserves changes", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    updateAgentMock.mockRejectedValue(new Error("network"));
    render(<AgentDetailPage />);
    const description = await screen.findByRole("textbox", {
      name: "Description",
    });
    await user.clear(description);
    await user.type(description, "Changed description");
    await user.click(
      screen.getAllByRole("button", { name: "Save configuration" })[0],
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The configuration could not be saved",
    );
    expect(description).toHaveValue("Changed description");
  });

  it("shows members a read-only configuration", async () => {
    authMock.role = "MEMBER";
    getAgentMock.mockResolvedValue(agent);
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("heading", { name: "Read-only configuration" }),
    ).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Agent name" })).toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: "Agent instructions" }),
    ).toBeDisabled();
    screen
      .getAllByRole("button", { name: "Save configuration" })
      .forEach((button) => expect(button).toBeDisabled());
    expect(screen.getByRole("button", { name: "Activate" })).toBeDisabled();
  });

  it("shows Mark Ready for draft agents", async () => {
    getAgentMock.mockResolvedValue({ ...agent, status: "DRAFT" });
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("button", { name: "Mark Ready" }),
    ).toBeEnabled();
    expect(
      screen.queryByRole("button", { name: "Activate" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Pause" }),
    ).not.toBeInTheDocument();
  });

  it("shows Activate for ready agents", async () => {
    getAgentMock.mockResolvedValue(agent);
    render(<AgentDetailPage />);
    expect(await screen.findByRole("button", { name: "Activate" })).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Mark Ready" }),
    ).not.toBeInTheDocument();
  });

  it("shows Pause for active agents", async () => {
    getAgentMock.mockResolvedValue({ ...agent, status: "ACTIVE" });
    render(<AgentDetailPage />);
    expect(await screen.findByRole("button", { name: "Pause" })).toBeVisible();
  });

  it("shows Resume for paused agents", async () => {
    getAgentMock.mockResolvedValue({ ...agent, status: "PAUSED" });
    render(<AgentDetailPage />);
    expect(await screen.findByRole("button", { name: "Resume" })).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Pause" }),
    ).not.toBeInTheDocument();
  });

  it("does not offer a fake resolve action for needs-attention agents", async () => {
    getAgentMock.mockResolvedValue({ ...agent, status: "NEEDS_ATTENTION" });
    render(<AgentDetailPage />);
    expect(
      await screen.findByText(
        "This agent needs attention and cannot change status from this screen.",
      ),
    ).toBeVisible();
    expect(screen.getAllByText("Needs attention").length).toBeGreaterThan(0);
    expect(
      screen.queryByRole("button", { name: "Mark Ready" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Activate" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Pause" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Resume" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/resolve/i)).not.toBeInTheDocument();
  });

  it.each(["OWNER", "ADMIN"] as const)(
    "lets %s confirm activate and updates the status from the API",
    async (role) => {
      const user = userEvent.setup();
      authMock.role = role;
      getAgentMock.mockResolvedValue(agent);
      activateAgentMock.mockResolvedValue({ ...agent, status: "ACTIVE" });
      render(<AgentDetailPage />);
      await user.click(await screen.findByRole("button", { name: "Activate" }));
      expect(
        screen.getByRole("heading", { name: "Activate this agent?" }),
      ).toBeVisible();
      await user.click(
        within(screen.getByRole("dialog")).getByRole("button", {
          name: "Activate",
        }),
      );
      expect(activateAgentMock).toHaveBeenCalledWith("agent-real-1");
      expect(await screen.findByRole("status")).toHaveTextContent(
        "Agent activated.",
      );
      expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
      expect(screen.getByRole("button", { name: "Pause" })).toBeVisible();
    },
  );

  it("cancels confirmation without requesting a lifecycle change", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    render(<AgentDetailPage />);
    await user.click(await screen.findByRole("button", { name: "Activate" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(activateAgentMock).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("heading", { name: "Activate this agent?" }),
    ).not.toBeInTheDocument();
  });

  it("shows a confirmation dialog before pausing", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue({ ...agent, status: "ACTIVE" });
    pauseAgentMock.mockResolvedValue({ ...agent, status: "PAUSED" });
    render(<AgentDetailPage />);
    await user.click(await screen.findByRole("button", { name: "Pause" }));
    expect(
      screen.getByRole("heading", { name: "Pause this agent?" }),
    ).toBeVisible();
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: "Pause" }),
    );
    expect(pauseAgentMock).toHaveBeenCalledWith("agent-real-1");
    expect(await screen.findByRole("status")).toHaveTextContent("Agent paused.");
  });

  it("marks a draft ready without a confirmation dialog", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue({ ...agent, status: "DRAFT" });
    markAgentReadyMock.mockResolvedValue({ ...agent, status: "READY" });
    render(<AgentDetailPage />);
    await user.click(await screen.findByRole("button", { name: "Mark Ready" }));
    expect(
      screen.queryByRole("heading", { name: /this agent/i }),
    ).not.toBeInTheDocument();
    expect(markAgentReadyMock).toHaveBeenCalledWith("agent-real-1");
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Agent marked ready.",
    );
  });

  it("shows lifecycle API errors without hiding the current status", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    activateAgentMock.mockRejectedValue(new ApiError("Request failed: 409", 409));
    render(<AgentDetailPage />);
    await user.click(await screen.findByRole("button", { name: "Activate" }));
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Activate",
      }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This status change is not allowed for the current agent.",
    );
    expect(screen.getAllByText("Ready").length).toBeGreaterThan(0);
  });

  it("prevents duplicate lifecycle submissions", async () => {
    const user = userEvent.setup();
    let resolveReady: (value: Agent) => void = () => undefined;
    getAgentMock.mockResolvedValue({ ...agent, status: "DRAFT" });
    markAgentReadyMock.mockReturnValue(
      new Promise((resolve) => {
        resolveReady = resolve;
      }),
    );
    render(<AgentDetailPage />);
    const markReady = await screen.findByRole("button", { name: "Mark Ready" });
    await user.click(markReady);
    expect(await screen.findByRole("button", { name: "Updating…" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Updating…" }));
    expect(markAgentReadyMock).toHaveBeenCalledTimes(1);
    resolveReady({ ...agent, status: "READY" });
    expect(await screen.findByRole("button", { name: "Activate" })).toBeVisible();
  });

  it("lets a READY agent execute and displays the API result", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    mockStartedRun();
    render(<AgentDetailPage />);
    const input = await screen.findByRole("textbox", {
      name: /Execution input/,
    });
    await user.type(input, "Qualify this lead");
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(createAgentExecutionMock).toHaveBeenCalledWith("agent-real-1", {
      input: "Qualify this lead",
    });
    expect(runAgentExecutionMock).toHaveBeenCalledWith(
      "agent-real-1",
      "exec-real-1",
    );
    expect(createAgentExecutionMock).toHaveBeenCalledTimes(1);
    expect(runAgentExecutionMock).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("This lead is qualified.")).toBeVisible();
    expect(screen.getByText("Completed")).toBeVisible();
    expect(screen.getByText("openai")).toBeVisible();
    expect(screen.getByText("gpt-4.1-mini")).toBeVisible();
    expect(screen.getByText("exec-real-1")).toBeVisible();
    expect(screen.getAllByText("Ready").length).toBeGreaterThan(0);
  });

  it("lets an ACTIVE agent execute", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue({ ...agent, status: "ACTIVE" });
    mockStartedRun();
    render(<AgentDetailPage />);
    const input = await screen.findByRole("textbox", {
      name: /Execution input/,
    });
    await user.type(input, "Follow up");
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(createAgentExecutionMock).toHaveBeenCalledWith("agent-real-1", {
      input: "Follow up",
    });
    expect(runAgentExecutionMock).toHaveBeenCalledWith(
      "agent-real-1",
      "exec-real-1",
    );
    expect(await screen.findByText("This lead is qualified.")).toBeVisible();
    expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
  });

  it("lets a MEMBER run an eligible agent", async () => {
    const user = userEvent.setup();
    authMock.role = "MEMBER";
    getAgentMock.mockResolvedValue(agent);
    mockStartedRun();
    render(<AgentDetailPage />);
    const input = await screen.findByRole("textbox", {
      name: /Execution input/,
    });
    await user.type(input, "Qualify this lead");
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(createAgentExecutionMock).toHaveBeenCalledTimes(1);
    expect(runAgentExecutionMock).toHaveBeenCalledTimes(1);
  });

  it.each([
    [
      "DRAFT",
      "Draft agents cannot be executed. Mark the agent ready first.",
    ],
    ["PAUSED", "Paused agents cannot be executed. Resume the agent first."],
    [
      "NEEDS_ATTENTION",
      "This agent needs attention and cannot be executed from this screen.",
    ],
  ] as const)("does not allow execution for %s agents", async (status, copy) => {
    getAgentMock.mockResolvedValue({ ...agent, status });
    render(<AgentDetailPage />);
    expect(await screen.findByText(copy)).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Run agent" }),
    ).not.toBeInTheDocument();
    expect(createAgentExecutionMock).not.toHaveBeenCalled();
    expect(runAgentExecutionMock).not.toHaveBeenCalled();
  });

  it("disables Run and prevents duplicate execution while running", async () => {
    const user = userEvent.setup();
    let resolveExecution: (value: AgentExecutionResult) => void = () =>
      undefined;
    getAgentMock.mockResolvedValue(agent);
    mockStartedRun(
      new Promise((resolve) => {
        resolveExecution = resolve;
      }),
    );
    render(<AgentDetailPage />);
    const input = await screen.findByRole("textbox", {
      name: /Execution input/,
    });
    await user.type(input, "Qualify this lead");
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByRole("button", { name: "Running…" })).toBeDisabled();
    expect(screen.getByText("Running agent…")).toBeVisible();
    expect(
      screen.getByText("Execution request in progress"),
    ).toBeVisible();
    expect(
      screen.getByRole("region", { name: "Run agent" }),
    ).toHaveAttribute("aria-busy", "true");
    await user.click(screen.getByRole("button", { name: "Running…" }));
    expect(createAgentExecutionMock).toHaveBeenCalledTimes(1);
    expect(runAgentExecutionMock).toHaveBeenCalledTimes(1);
    resolveExecution(executionResult);
    expect(await screen.findByText("This lead is qualified.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Run agent" })).toBeEnabled();
    expect(
      screen.queryByRole("button", { name: "Cancel execution" }),
    ).not.toBeInTheDocument();
  });

  it("cancels a running execution through the API", async () => {
    const user = userEvent.setup();
    let resolveRun: (value: AgentExecutionResult) => void = () => undefined;
    let resolveCancel: (value: AgentExecutionResult) => void = () => undefined;
    getAgentMock.mockResolvedValue(agent);
    createAgentExecutionMock.mockResolvedValue(startedExecution);
    runAgentExecutionMock.mockReturnValue(
      new Promise((resolve) => {
        resolveRun = resolve;
      }),
    );
    cancelAgentExecutionMock.mockReturnValue(
      new Promise((resolve) => {
        resolveCancel = resolve;
      }),
    );
    render(<AgentDetailPage />);
    await user.type(
      await screen.findByRole("textbox", { name: /Execution input/ }),
      "Qualify this lead",
    );
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    const cancel = await screen.findByRole("button", {
      name: "Cancel execution",
    });
    expect(cancel).toBeEnabled();
    await user.click(cancel);
    expect(await screen.findByRole("button", { name: "Cancelling…" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Cancelling…" }));
    expect(cancelAgentExecutionMock).toHaveBeenCalledTimes(1);
    expect(cancelAgentExecutionMock).toHaveBeenCalledWith(
      "agent-real-1",
      "exec-real-1",
    );
    resolveCancel({
      execution_id: "exec-real-1",
      status: "CANCELLED",
      output: null,
      provider: null,
      model: null,
      usage: null,
      error: "Execution was cancelled.",
    });
    expect(await screen.findByText("Cancelled")).toBeVisible();
    expect(screen.getByText("Execution was cancelled.")).toBeVisible();
    resolveRun({
      execution_id: "exec-real-1",
      status: "CANCELLED",
      output: null,
      provider: null,
      model: null,
      usage: null,
      error: "Execution was cancelled.",
    });
    expect(
      screen.queryByRole("button", { name: "Cancel execution" }),
    ).not.toBeInTheDocument();
    expect(listAgentExecutionsMock.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("shows a conflict message when cancellation is no longer allowed", async () => {
    const user = userEvent.setup();
    let resolveRun: (value: AgentExecutionResult) => void = () => undefined;
    getAgentMock.mockResolvedValue(agent);
    createAgentExecutionMock.mockResolvedValue(startedExecution);
    runAgentExecutionMock.mockReturnValue(
      new Promise((resolve) => {
        resolveRun = resolve;
      }),
    );
    cancelAgentExecutionMock.mockRejectedValue(
      new ApiError("Request failed: 409", 409),
    );
    render(<AgentDetailPage />);
    await user.type(
      await screen.findByRole("textbox", { name: /Execution input/ }),
      "Qualify this lead",
    );
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    await user.click(
      await screen.findByRole("button", { name: "Cancel execution" }),
    );
    expect(
      await screen.findByText("This execution can no longer be cancelled."),
    ).toBeVisible();
    expect(cancelAgentExecutionMock).toHaveBeenCalledTimes(1);
    resolveRun(executionResult);
    expect(await screen.findByText("This lead is qualified.")).toBeVisible();
  });

  it("renders cancelled history without a failure category", async () => {
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock.mockResolvedValue({
      items: [
        historyItem("exec-cancelled-1", {
          status: "CANCELLED",
          duration_ms: 1800,
          failure_category: null,
          error_preview: "Execution was cancelled.",
        }),
      ],
      limit: 20,
      offset: 0,
      total: 1,
    });
    render(<AgentDetailPage />);
    expect(await screen.findByText("Cancelled · 1.8s")).toBeVisible();
    expect(screen.queryByText("Provider error")).not.toBeInTheDocument();
  });

  it("submits only once when Enter is pressed repeatedly on Run agent", async () => {
    const user = userEvent.setup();
    let resolveExecution: (value: AgentExecutionResult) => void = () =>
      undefined;
    getAgentMock.mockResolvedValue(agent);
    mockStartedRun(
      new Promise((resolve) => {
        resolveExecution = resolve;
      }),
    );
    render(<AgentDetailPage />);
    await user.type(
      await screen.findByRole("textbox", { name: /Execution input/ }),
      "Qualify this lead",
    );
    const run = screen.getByRole("button", { name: "Run agent" });
    run.focus();
    await user.keyboard("{Enter}");
    await user.keyboard("{Enter}");
    expect(createAgentExecutionMock).toHaveBeenCalledTimes(1);
    expect(runAgentExecutionMock).toHaveBeenCalledTimes(1);
    resolveExecution(executionResult);
    expect(await screen.findByText("This lead is qualified.")).toBeVisible();
  });

  it("re-enables Run agent after a failed request", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    createAgentExecutionMock.mockResolvedValue(startedExecution);
    runAgentExecutionMock.mockRejectedValue(new Error("network"));
    render(<AgentDetailPage />);
    const input = await screen.findByRole("textbox", {
      name: /Execution input/,
    });
    await user.type(input, "Qualify this lead");
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The agent could not be run. Check your connection and try again.",
    );
    expect(screen.getByRole("button", { name: "Run agent" })).toBeEnabled();
    expect(input).toHaveValue("Qualify this lead");
  });

  it("shows duration and usage on a successful result without a failure category", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    mockStartedRun({
      ...executionResult,
      duration_ms: 1800,
    });
    render(<AgentDetailPage />);
    await user.type(
      await screen.findByRole("textbox", { name: /Execution input/ }),
      "Qualify this lead",
    );
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByText("This lead is qualified.")).toBeVisible();
    expect(screen.getByText("1.8s")).toBeVisible();
    expect(screen.getByText("42")).toBeVisible();
    expect(screen.queryByText("Failure category")).not.toBeInTheDocument();
    expect(screen.queryByText("Provider error")).not.toBeInTheDocument();
  });

  it("shows a failed execution result with category and duration", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    mockStartedRun({
      execution_id: "exec-failed-1",
      status: "FAILED",
      output: null,
      provider: "openai",
      model: "gpt-4.1-mini",
      usage: null,
      error: "The AI provider could not complete this run.",
      duration_ms: 2400,
      failure_category: "PROVIDER_ERROR",
    });
    render(<AgentDetailPage />);
    await user.type(
      await screen.findByRole("textbox", { name: /Execution input/ }),
      "Qualify this lead",
    );
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByText("Failed")).toBeVisible();
    expect(screen.getByText("Provider error")).toBeVisible();
    expect(screen.getByText("2.4s")).toBeVisible();
    expect(
      screen.getByText("The AI provider could not complete this run."),
    ).toBeVisible();
    expect(screen.queryByText("sk-secret")).not.toBeInTheDocument();
    expect(screen.queryByText("tool_results")).not.toBeInTheDocument();
    expect(
      screen.getByRole("textbox", { name: /Execution input/ }),
    ).toHaveValue("Qualify this lead");
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  it("retries the same input through Try again", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    createAgentExecutionMock.mockResolvedValue(startedExecution);
    runAgentExecutionMock
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(executionResult);
    render(<AgentDetailPage />);
    await user.type(
      await screen.findByRole("textbox", { name: /Execution input/ }),
      "Qualify this lead",
    );
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    await user.click(await screen.findByRole("button", { name: "Try again" }));
    expect(createAgentExecutionMock).toHaveBeenCalledTimes(2);
    expect(runAgentExecutionMock).toHaveBeenCalledTimes(2);
    expect(createAgentExecutionMock).toHaveBeenLastCalledWith("agent-real-1", {
      input: "Qualify this lead",
    });
    expect(runAgentExecutionMock).toHaveBeenLastCalledWith(
      "agent-real-1",
      "exec-real-1",
    );
    expect(await screen.findByText("This lead is qualified.")).toBeVisible();
  });

  it("refreshes history after a persisted provider failure", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock
      .mockResolvedValueOnce(emptyHistory)
      .mockResolvedValue({
        items: [
          historyItem("exec-failed-1", {
            status: "FAILED",
            failure_category: "PROVIDER_ERROR",
          }),
        ],
        limit: 20,
        offset: 0,
        total: 1,
      });
    createAgentExecutionMock.mockResolvedValue({
      ...startedExecution,
      execution_id: "exec-failed-1",
    });
    runAgentExecutionMock.mockRejectedValue(
      new ApiError("Request failed: 502", 502),
    );
    render(<AgentDetailPage />);
    expect(
      await screen.findByText(
        /No executions have been recorded for this agent yet/,
      ),
    ).toBeVisible();
    await user.type(
      screen.getByRole("textbox", { name: /Execution input/ }),
      "Qualify this lead",
    );
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The AI provider could not complete this run.",
    );
    expect(
      await screen.findByRole("button", { name: "View execution exec-failed-1" }),
    ).toBeVisible();
    expect(listAgentExecutionsMock).toHaveBeenCalledTimes(2);
  });

  it("does not erase a previous result when a later request fails", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    createAgentExecutionMock.mockResolvedValue(startedExecution);
    runAgentExecutionMock
      .mockResolvedValueOnce(executionResult)
      .mockRejectedValueOnce(new ApiError("Request failed: 400", 400));
    render(<AgentDetailPage />);
    await user.type(
      await screen.findByRole("textbox", { name: /Execution input/ }),
      "Qualify this lead",
    );
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByText("This lead is qualified.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This agent cannot be executed in its current status.",
    );
    expect(screen.getByText("This lead is qualified.")).toBeVisible();
  });

  it.each([
    [400, "This agent cannot be executed in its current status."],
    [401, "Your session has expired. Sign in again to run this agent."],
    [403, "You do not have permission to run this agent."],
    [404, "This agent could not be found."],
    [422, "Review the execution input and try again."],
    [502, "The AI provider could not complete this run."],
    [503, "The AI provider is not configured."],
  ] as const)("handles execution HTTP %s", async (status, message) => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    createAgentExecutionMock.mockResolvedValue(startedExecution);
    runAgentExecutionMock.mockRejectedValue(
      new ApiError(`Request failed: ${status}`, status),
    );
    render(<AgentDetailPage />);
    const input = await screen.findByRole("textbox", {
      name: /Execution input/,
    });
    await user.type(input, "Qualify this lead");
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getAllByText("Ready").length).toBeGreaterThan(0);
  });

  it("handles execution network failure", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    createAgentExecutionMock.mockResolvedValue(startedExecution);
    runAgentExecutionMock.mockRejectedValue(new Error("network"));
    render(<AgentDetailPage />);
    const input = await screen.findByRole("textbox", {
      name: /Execution input/,
    });
    await user.type(input, "Qualify this lead");
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The agent could not be run. Check your connection and try again.",
    );
    expect(screen.getAllByText("Ready").length).toBeGreaterThan(0);
  });

  it("shows a loading state for execution history", async () => {
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock.mockReturnValue(new Promise(() => undefined));
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("heading", { name: "Inbound qualifier" }),
    ).toBeVisible();
    expect(screen.getByText("Loading execution history")).toBeVisible();
  });

  it("shows an empty execution history", async () => {
    getAgentMock.mockResolvedValue(agent);
    render(<AgentDetailPage />);
    expect(
      await screen.findByText(
        /No executions have been recorded for this agent yet/,
      ),
    ).toBeVisible();
    expect(listAgentExecutionsMock).toHaveBeenCalledWith("agent-real-1", {
      limit: 20,
      offset: 0,
    });
  });

  it("retries a failed history load", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(emptyHistory);
    render(<AgentDetailPage />);
    expect(
      await screen.findByText(/Execution history could not be loaded/),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Inbound qualifier" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry history" }));
    expect(
      await screen.findByText(
        /No executions have been recorded for this agent yet/,
      ),
    ).toBeVisible();
  });

  it("renders history list fields without full input or output", async () => {
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock.mockResolvedValue({
      items: [
        historyItem("exec-list-1", {
          input_preview: "Preview of the run",
          error_preview: "Provider timeout",
        }),
      ],
      limit: 20,
      offset: 0,
      total: 1,
    });
    render(<AgentDetailPage />);
    expect(await screen.findByText("Preview of the run")).toBeVisible();
    expect(screen.getByText("Provider timeout")).toBeVisible();
    expect(screen.getByText("openai")).toBeVisible();
    expect(screen.getByText("gpt-4o-mini")).toBeVisible();
    expect(
      screen.queryByText("Qualify this lead with confidential context"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("This lead is fully qualified after review."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("tool_results")).not.toBeInTheDocument();
    expect(screen.getByText("Completed · 2s")).toBeVisible();
    expect(screen.queryByText("Provider error")).not.toBeInTheDocument();
  });

  it("renders failure category and duration for a failed history item", async () => {
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock.mockResolvedValue({
      items: [
        historyItem("exec-list-1", {
          status: "FAILED",
          duration_ms: 2400,
          failure_category: "PROVIDER_ERROR",
          error_preview: "upstream timeout",
        }),
      ],
      limit: 20,
      offset: 0,
      total: 1,
    });
    render(<AgentDetailPage />);
    expect(await screen.findByText("Failed · Provider error · 2.4s")).toBeVisible();
  });

  it("paginates execution history using limit and offset", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    const items = Array.from({ length: 43 }, (_, index) =>
      historyItem(`exec-page-${index + 1}`, {
        input_preview: `Preview ${index + 1}`,
      }),
    );
    listAgentExecutionsMock.mockImplementation(
      async (_id: string, params?: { limit?: number; offset?: number }) => {
        const limit = params?.limit ?? 20;
        const offset = params?.offset ?? 0;
        return {
          items: items.slice(offset, offset + limit),
          limit,
          offset,
          total: 43,
        };
      },
    );
    render(<AgentDetailPage />);
    expect(await screen.findByText("Showing 1–20 of 43")).toBeVisible();
    expect(screen.getByText("Preview 1")).toBeVisible();
    expect(screen.queryByText("Preview 21")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Previous executions page" }),
    ).toBeDisabled();
    await user.click(
      screen.getByRole("button", { name: "Next executions page" }),
    );
    expect(await screen.findByText("Showing 21–40 of 43")).toBeVisible();
    expect(listAgentExecutionsMock).toHaveBeenCalledWith("agent-real-1", {
      limit: 20,
      offset: 20,
    });
    await user.click(
      screen.getByRole("button", { name: "Next executions page" }),
    );
    expect(await screen.findByText("Showing 41–43 of 43")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Next executions page" }),
    ).toBeDisabled();
    await user.click(
      screen.getByRole("button", { name: "Previous executions page" }),
    );
    expect(await screen.findByText("Showing 21–40 of 43")).toBeVisible();
  });

  it("loads execution detail and tool activity for a selected run", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock.mockResolvedValue({
      items: [historyItem("exec-list-1")],
      limit: 20,
      offset: 0,
      total: 1,
    });
    const detail: AgentExecutionDetail = {
      id: "exec-list-1",
      agent_id: "agent-real-1",
      status: "COMPLETED",
      input: "Qualify this lead with confidential context",
      output: "This lead is fully qualified after review.",
      provider: "openai",
      model: "gpt-4o-mini",
      usage: { total_tokens: 12 },
      error: null,
      started_at: "2026-09-09T10:00:00Z",
      completed_at: "2026-09-09T10:00:02Z",
      created_at: "2026-09-09T10:00:00Z",
      initiated_by_user_id: "user-1",
      duration_ms: 2000,
      failure_category: null,
    };
    getAgentExecutionMock.mockResolvedValue(detail);
    const invocation: ToolInvocationListItem = {
      id: "inv-1",
      execution_id: "exec-list-1",
      agent_id: "agent-real-1",
      call_id: "call-1",
      tool_name: "echo",
      risk_level: "LOW",
      decision: "ALLOW",
      status: "SUCCESS",
      argument_keys: ["message"],
      error: null,
      started_at: "2026-09-09T10:00:01Z",
      completed_at: "2026-09-09T10:00:01Z",
      created_at: "2026-09-09T10:00:01Z",
      duration_ms: 420,
    };
    listToolInvocationsMock.mockResolvedValue({
      items: [invocation],
      limit: 50,
      offset: 0,
      total: 1,
    });
    render(<AgentDetailPage />);
    await user.click(
      await screen.findByRole("button", { name: "View execution exec-list-1" }),
    );
    expect(getAgentExecutionMock).toHaveBeenCalledWith(
      "agent-real-1",
      "exec-list-1",
    );
    expect(
      await screen.findByText("Qualify this lead with confidential context"),
    ).toBeVisible();
    expect(
      screen.getByText("This lead is fully qualified after review."),
    ).toBeVisible();
    expect(screen.getByText("12")).toBeVisible();
    expect(screen.getByText("user-1")).toBeVisible();
    expect(listToolInvocationsMock).toHaveBeenCalledWith(
      "agent-real-1",
      "exec-list-1",
      { limit: 50, offset: 0 },
    );
    expect(screen.getByText("echo")).toBeVisible();
    expect(screen.getByText("420ms")).toBeVisible();
    expect(screen.getAllByText("2s").length).toBeGreaterThan(0);
    expect(screen.getByText("message")).toBeVisible();
    expect(screen.getByText("LOW")).toBeVisible();
    expect(screen.getByText("ALLOW")).toBeVisible();
    expect(screen.queryByText("hello secret")).not.toBeInTheDocument();
    expect(screen.queryByText("tool_results")).not.toBeInTheDocument();
  });

  it("keeps execution detail when tool activity fails", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock.mockResolvedValue({
      items: [historyItem("exec-list-1")],
      limit: 20,
      offset: 0,
      total: 1,
    });
    getAgentExecutionMock.mockResolvedValue({
      id: "exec-list-1",
      agent_id: "agent-real-1",
      status: "FAILED",
      input: "Task input",
      output: null,
      provider: null,
      model: null,
      usage: null,
      error: "The AI provider could not complete this run.",
      started_at: "2026-09-09T10:00:00Z",
      completed_at: null,
      created_at: "2026-09-09T10:00:00Z",
      initiated_by_user_id: null,
      duration_ms: null,
      failure_category: "PROVIDER_ERROR",
    });
    listToolInvocationsMock.mockRejectedValue(new Error("network"));
    render(<AgentDetailPage />);
    await user.click(
      await screen.findByRole("button", { name: "View execution exec-list-1" }),
    );
    expect(await screen.findByText("Task input")).toBeVisible();
    expect(
      screen.getByText("The AI provider could not complete this run."),
    ).toBeVisible();
    expect(screen.queryByText("Provider token usage")).not.toBeInTheDocument();
    expect(
      await screen.findByText(/Tool activity could not be loaded/),
    ).toBeVisible();
  });

  it("shows an empty tool activity state", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock.mockResolvedValue({
      items: [historyItem("exec-list-1")],
      limit: 20,
      offset: 0,
      total: 1,
    });
    getAgentExecutionMock.mockResolvedValue({
      id: "exec-list-1",
      agent_id: "agent-real-1",
      status: "COMPLETED",
      input: "Task input",
      output: "Done",
      provider: "openai",
      model: "gpt-4o-mini",
      usage: null,
      error: null,
      started_at: "2026-09-09T10:00:00Z",
      completed_at: "2026-09-09T10:00:02Z",
      created_at: "2026-09-09T10:00:00Z",
      initiated_by_user_id: null,
      duration_ms: 2000,
      failure_category: null,
    });
    render(<AgentDetailPage />);
    await user.click(
      await screen.findByRole("button", { name: "View execution exec-list-1" }),
    );
    expect(
      await screen.findByText("No tool activity recorded for this execution."),
    ).toBeVisible();
  });

  it("handles execution detail 404", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock.mockResolvedValue({
      items: [historyItem("exec-list-1")],
      limit: 20,
      offset: 0,
      total: 1,
    });
    getAgentExecutionMock.mockRejectedValue(new ApiError("Request failed: 404", 404));
    render(<AgentDetailPage />);
    await user.click(
      await screen.findByRole("button", { name: "View execution exec-list-1" }),
    );
    expect(
      await screen.findByText("This execution could not be found."),
    ).toBeVisible();
  });

  it.each(["OWNER", "ADMIN", "MEMBER"] as const)(
    "lets %s view execution history",
    async (role) => {
      authMock.role = role;
      getAgentMock.mockResolvedValue(agent);
      listAgentExecutionsMock.mockResolvedValue({
        items: [historyItem("exec-list-1")],
        limit: 20,
        offset: 0,
        total: 1,
      });
      render(<AgentDetailPage />);
      expect(
        await screen.findByRole("button", { name: "View execution exec-list-1" }),
      ).toBeVisible();
    },
  );

  it("refreshes history after a successful manual run", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock
      .mockResolvedValueOnce(emptyHistory)
      .mockResolvedValue({
        items: [historyItem("exec-real-1")],
        limit: 20,
        offset: 0,
        total: 1,
      });
    mockStartedRun();
    render(<AgentDetailPage />);
    expect(
      await screen.findByText(
        /No executions have been recorded for this agent yet/,
      ),
    ).toBeVisible();
    await user.type(
      screen.getByRole("textbox", { name: /Execution input/ }),
      "Qualify this lead",
    );
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByText("This lead is qualified.")).toBeVisible();
    expect(
      await screen.findByRole("button", { name: "View execution exec-real-1" }),
    ).toBeVisible();
    expect(listAgentExecutionsMock).toHaveBeenCalledTimes(2);
  });

  it("keeps the run result if history refresh fails", async () => {
    const user = userEvent.setup();
    getAgentMock.mockResolvedValue(agent);
    listAgentExecutionsMock
      .mockResolvedValueOnce(emptyHistory)
      .mockRejectedValue(new Error("network"));
    mockStartedRun();
    render(<AgentDetailPage />);
    await user.type(
      await screen.findByRole("textbox", { name: /Execution input/ }),
      "Qualify this lead",
    );
    await user.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByText("This lead is qualified.")).toBeVisible();
    expect(
      await screen.findByText(/Execution history could not be loaded/),
    ).toBeVisible();
  });

  it("shows sales runs for SALES agents", async () => {
    getAgentMock.mockResolvedValue(agent);
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("heading", { name: "Sales runs" }),
    ).toBeVisible();
    expect(listSalesRunsMock).toHaveBeenCalledWith("agent-real-1");
  });

  it("hides sales runs for OPERATIONS agents", async () => {
    getAgentMock.mockResolvedValue({ ...agent, agent_type: "OPERATIONS" });
    render(<AgentDetailPage />);
    expect(
      await screen.findByRole("heading", { level: 1, name: "Inbound qualifier" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Sales runs" }),
    ).not.toBeInTheDocument();
  });
});
