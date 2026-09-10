import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  activateAgent,
  createAgent,
  createAgentExecution,
  executeAgent,
  getAgent,
  getAgentExecution,
  getAgents,
  listAgentExecutions,
  listToolInvocations,
  markAgentReady,
  pauseAgent,
  runAgentExecution,
  updateAgent,
} from "@/lib/api/agents";
import type {
  AgentExecutionDetail,
  AgentExecutionListResponse,
  ToolInvocationListResponse,
} from "@/types/api";

describe("Agent API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("flowpilot.access_token", "agent-token");
  });

  it("gets the authenticated agent list endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await getAgents();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer agent-token",
        }),
      }),
    );
  });

  it("uses backend-supported status and agent_type query parameters", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await getAgents({ status: "ACTIVE", agentType: "SALES" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents?status=ACTIVE&agent_type=SALES",
      expect.any(Object),
    );
  });

  it("gets an encoded agent detail endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "agent/1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await getAgent("agent/1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent%2F1",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("preserves global 401 session invalidation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid token" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(getAgents()).rejects.toMatchObject({ status: 401 });
    expect(window.localStorage.getItem("flowpilot.access_token")).toBeNull();
  });

  it("posts only the supported create payload", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "new-agent" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const payload = {
      name: "Support agent",
      description: "Handles support.",
      agent_type: "SUPPORT" as const,
      system_instructions: "Be concise.",
    };
    await createAgent(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
  });

  it("patches changed configuration through the authenticated client", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "agent-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await updateAgent("agent-1", { name: "Renamed" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ name: "Renamed" }),
        headers: expect.objectContaining({
          Authorization: "Bearer agent-token",
        }),
      }),
    );
  });

  it.each([
    ["ready", markAgentReady],
    ["activate", activateAgent],
    ["pause", pauseAgent],
  ] as const)("posts %s without a request body", async (action, method) => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "agent-1", status: "READY" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await method("agent/1");
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/api/v1/agents/agent%2F1/${action}`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer agent-token",
        }),
      }),
    );
    expect(fetchMock.mock.calls[0]?.[1]).not.toHaveProperty("body", expect.anything());
    expect(fetchMock.mock.calls[0]?.[1]?.body).toBeUndefined();
  });

  it("posts execution input without organization_id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          execution_id: "exec-1",
          status: "COMPLETED",
          output: "Qualified",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    await executeAgent("agent/1", { input: "Qualify this lead" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent%2F1/execute",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ input: "Qualify this lead" }),
        headers: expect.objectContaining({
          Authorization: "Bearer agent-token",
        }),
      }),
    );
    expect(fetchMock.mock.calls[0]?.[1]?.body).not.toContain("organization_id");
  });

  it("creates an execution without running the provider", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          execution_id: "exec/1",
          status: "RUNNING",
          started_at: "2026-09-09T10:00:00Z",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    const started = await createAgentExecution("agent/1", {
      input: "Qualify this lead",
    });
    expect(started.status).toBe("RUNNING");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent%2F1/executions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ input: "Qualify this lead" }),
      }),
    );
    expect(fetchMock.mock.calls[0]?.[1]?.body).not.toContain("organization_id");
  });

  it("runs an encoded execution id without a request body", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          execution_id: "exec/1",
          status: "COMPLETED",
          output: "Qualified",
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    await runAgentExecution("agent/1", "exec/1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent%2F1/executions/exec%2F1/run",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer agent-token",
        }),
      }),
    );
    expect(fetchMock.mock.calls[0]?.[1]?.body).toBeUndefined();
  });

  it("recovers a persisted failed execution from a 502 body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          execution_id: "exec-fail-1",
          status: "FAILED",
          output: null,
          provider: "openai",
          model: "gpt-4.1-mini",
          usage: null,
          error: "AI provider request failed",
          detail: "AI provider request failed",
          arguments: { secret: "sk-live" },
          tool_results: [{ output: "hidden" }],
        }),
        {
          status: 502,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    const result = await executeAgent("agent-1", { input: "Qualify this lead" });
    expect(result).toEqual({
      execution_id: "exec-fail-1",
      status: "FAILED",
      output: null,
      provider: "openai",
      model: "gpt-4.1-mini",
      usage: null,
      error: "AI provider request failed",
      duration_ms: null,
      failure_category: null,
    });
    expect(JSON.stringify(result)).not.toContain("sk-live");
    expect(JSON.stringify(result)).not.toContain("tool_results");
  });

  it("recovers a failed run response from a 502 body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          execution_id: "exec-fail-1",
          status: "FAILED",
          output: null,
          provider: "openai",
          model: "gpt-4.1-mini",
          usage: null,
          error: "AI provider request failed",
          detail: "AI provider request failed",
        }),
        {
          status: 502,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    const result = await runAgentExecution("agent-1", "exec-fail-1");
    expect(result.status).toBe("FAILED");
    expect(result.execution_id).toBe("exec-fail-1");
  });

  it("throws when a 502 body is not a failed execution result", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "upstream" }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(
      executeAgent("agent-1", { input: "Qualify this lead" }),
    ).rejects.toMatchObject({ status: 502 });
  });

  const completedList: AgentExecutionListResponse = {
    items: [
      {
        id: "exec-1",
        status: "COMPLETED",
        provider: "openai",
        model: "gpt-4o-mini",
        started_at: "2026-09-09T10:00:00Z",
        completed_at: "2026-09-09T10:00:02Z",
        created_at: "2026-09-09T10:00:00Z",
        input_preview: "Qualify this lead",
        error_preview: null,
        duration_ms: 2000,
        failure_category: null,
      },
    ],
    limit: 20,
    offset: 0,
    total: 1,
  };

  const failedDetail: AgentExecutionDetail = {
    id: "exec/2",
    agent_id: "agent/1",
    status: "FAILED",
    input: "Summarize the ticket",
    output: null,
    provider: null,
    model: null,
    usage: null,
    error: "The AI provider could not complete this run.",
    started_at: "2026-09-09T11:00:00Z",
    completed_at: null,
    created_at: "2026-09-09T11:00:00Z",
    initiated_by_user_id: null,
    duration_ms: null,
    failure_category: "PROVIDER_ERROR",
  };

  const invocations: ToolInvocationListResponse = {
    items: [
      {
        id: "inv-1",
        execution_id: "exec-1",
        agent_id: "agent-1",
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
        duration_ms: 0,
      },
      {
        id: "inv-2",
        execution_id: "exec-1",
        agent_id: "agent-1",
        call_id: "call-2",
        tool_name: "echo",
        risk_level: null,
        decision: null,
        status: "FAILED",
        argument_keys: null,
        error: "Invalid tool arguments",
        started_at: "2026-09-09T10:00:02Z",
        completed_at: "2026-09-09T10:00:02Z",
        created_at: "2026-09-09T10:00:02Z",
        duration_ms: 0,
      },
    ],
    limit: 20,
    offset: 0,
    total: 2,
  };

  it("lists executions with encoded agent id and optional pagination", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(completedList), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const result = await listAgentExecutions("agent/1", { limit: 10, offset: 20 });
    expect(result).toEqual(completedList);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent%2F1/executions?limit=10&offset=20",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer agent-token",
        }),
      }),
    );
    expect(fetchMock.mock.calls[0]?.[0]).not.toContain("organization_id");
  });

  it("clamps execution history query parameters to API bounds", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(completedList), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await listAgentExecutions("agent-1", { limit: 99, offset: -4 });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent-1/executions?limit=50&offset=0",
      expect.any(Object),
    );
  });

  it("omits unused execution list query parameters", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(completedList), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await listAgentExecutions("agent-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent-1/executions",
      expect.any(Object),
    );
  });

  it("propagates execution list API errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Agent not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(listAgentExecutions("missing")).rejects.toMatchObject({
      status: 404,
    });
  });

  it("gets encoded execution detail without organization_id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(failedDetail), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const result = await getAgentExecution("agent/1", "exec/2");
    expect(result).toEqual(failedDetail);
    expect(result.usage).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent%2F1/executions/exec%2F2",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock.mock.calls[0]?.[0]).not.toContain("organization_id");
  });

  it("returns execution detail usage when the backend includes it", async () => {
    const completed: AgentExecutionDetail = {
      ...failedDetail,
      id: "exec-3",
      status: "COMPLETED",
      output: "The lead is qualified.",
      provider: "openai",
      model: "gpt-4o-mini",
      usage: { prompt_tokens: 3, completion_tokens: 5, total_tokens: 8 },
      error: null,
      completed_at: "2026-09-09T11:00:02Z",
      initiated_by_user_id: "user-1",
      duration_ms: 2000,
      failure_category: null,
    };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(completed), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(getAgentExecution("agent-1", "exec-3")).resolves.toEqual(
      completed,
    );
  });

  it("lists tool invocations with pagination and key names only", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(invocations), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const result = await listToolInvocations("agent/1", "exec/2", {
      limit: 5,
      offset: 0,
    });
    expect(result).toEqual(invocations);
    expect(result.items[0]?.argument_keys).toEqual(["message"]);
    expect(JSON.stringify(result)).not.toContain("tool_results");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent%2F1/executions/exec%2F2/tool-invocations?limit=5&offset=0",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock.mock.calls[0]?.[0]).not.toContain("organization_id");
  });
});
