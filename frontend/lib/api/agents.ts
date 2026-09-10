import { ApiError, apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  Agent,
  AgentCreateRequest,
  AgentExecutionCreated,
  AgentExecutionDetail,
  AgentExecutionListResponse,
  AgentExecutionRequest,
  AgentExecutionResult,
  AgentListResponse,
  AgentStatus,
  AgentType,
  AgentUpdateRequest,
  ExecutionFailureCategory,
  ToolInvocationListResponse,
} from "@/types/api";

export type AgentListFilters = {
  status?: AgentStatus;
  agentType?: AgentType;
};

export type AgentHistoryPageParams = {
  limit?: number;
  offset?: number;
};

function historyQuery(params: AgentHistoryPageParams = {}) {
  const query = new URLSearchParams();
  if (params.limit !== undefined) {
    const limit = Math.min(50, Math.max(1, Math.trunc(params.limit)));
    query.set("limit", String(Number.isFinite(limit) ? limit : 20));
  }
  if (params.offset !== undefined) {
    const offset = Math.max(0, Math.trunc(params.offset));
    query.set("offset", String(Number.isFinite(offset) ? offset : 0));
  }
  return query.size > 0 ? `?${query.toString()}` : "";
}

export function getAgents(filters: AgentListFilters = {}) {
  const query = new URLSearchParams();
  if (filters.status) {
    query.set("status", filters.status);
  }
  if (filters.agentType) {
    query.set("agent_type", filters.agentType);
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiGet<AgentListResponse>(`/api/v1/agents${suffix}`);
}

export function getAgent(agentId: string) {
  return apiGet<Agent>(`/api/v1/agents/${encodeURIComponent(agentId)}`);
}

export function createAgent(input: AgentCreateRequest) {
  return apiPost<Agent>("/api/v1/agents", input);
}

export function updateAgent(agentId: string, input: AgentUpdateRequest) {
  return apiPatch<Agent>(
    `/api/v1/agents/${encodeURIComponent(agentId)}`,
    input,
  );
}

function agentActionPath(agentId: string, action: "ready" | "activate" | "pause") {
  return `/api/v1/agents/${encodeURIComponent(agentId)}/${action}`;
}

export function markAgentReady(agentId: string) {
  return apiPost<Agent>(agentActionPath(agentId, "ready"));
}

export function activateAgent(agentId: string) {
  return apiPost<Agent>(agentActionPath(agentId, "activate"));
}

export function pauseAgent(agentId: string) {
  return apiPost<Agent>(agentActionPath(agentId, "pause"));
}

const FAILURE_CATEGORIES = new Set<ExecutionFailureCategory>([
  "PROVIDER_ERROR",
  "TOOL_ERROR",
  "POLICY_ERROR",
  "VALIDATION_ERROR",
  "EXECUTION_ERROR",
  "CONFIGURATION_ERROR",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function recoverFailedExecution(cause: unknown): AgentExecutionResult | null {
  if (!(cause instanceof ApiError)) return null;
  if (cause.status !== 502 && cause.status !== 503) return null;
  if (!isRecord(cause.body)) return null;
  if (typeof cause.body.execution_id !== "string") return null;
  if (cause.body.status !== "FAILED") return null;

  const usage = isRecord(cause.body.usage)
    ? {
        prompt_tokens:
          typeof cause.body.usage.prompt_tokens === "number"
            ? cause.body.usage.prompt_tokens
            : null,
        completion_tokens:
          typeof cause.body.usage.completion_tokens === "number"
            ? cause.body.usage.completion_tokens
            : null,
        total_tokens:
          typeof cause.body.usage.total_tokens === "number"
            ? cause.body.usage.total_tokens
            : null,
      }
    : null;
  const duration =
    typeof cause.body.duration_ms === "number" &&
    Number.isFinite(cause.body.duration_ms) &&
    cause.body.duration_ms >= 0
      ? Math.trunc(cause.body.duration_ms)
      : null;
  const category = FAILURE_CATEGORIES.has(
    cause.body.failure_category as ExecutionFailureCategory,
  )
    ? (cause.body.failure_category as ExecutionFailureCategory)
    : null;
  const error =
    typeof cause.body.error === "string"
      ? cause.body.error
      : typeof cause.body.detail === "string"
        ? cause.body.detail
        : null;

  return {
    execution_id: cause.body.execution_id,
    status: "FAILED",
    output: typeof cause.body.output === "string" ? cause.body.output : null,
    provider: typeof cause.body.provider === "string" ? cause.body.provider : null,
    model: typeof cause.body.model === "string" ? cause.body.model : null,
    usage,
    error,
    duration_ms: duration,
    failure_category: category,
  };
}

export async function executeAgent(
  agentId: string,
  input: AgentExecutionRequest,
) {
  try {
    return await apiPost<AgentExecutionResult>(
      `/api/v1/agents/${encodeURIComponent(agentId)}/execute`,
      input,
    );
  } catch (cause) {
    const recovered = recoverFailedExecution(cause);
    if (recovered) return recovered;
    throw cause;
  }
}

export function createAgentExecution(
  agentId: string,
  input: AgentExecutionRequest,
) {
  return apiPost<AgentExecutionCreated>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/executions`,
    input,
  );
}

export async function runAgentExecution(agentId: string, executionId: string) {
  try {
    return await apiPost<AgentExecutionResult>(
      `/api/v1/agents/${encodeURIComponent(agentId)}/executions/${encodeURIComponent(executionId)}/run`,
    );
  } catch (cause) {
    const recovered = recoverFailedExecution(cause);
    if (recovered) return recovered;
    throw cause;
  }
}

export function listAgentExecutions(
  agentId: string,
  params: AgentHistoryPageParams = {},
) {
  return apiGet<AgentExecutionListResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/executions${historyQuery(params)}`,
  );
}

export function getAgentExecution(agentId: string, executionId: string) {
  return apiGet<AgentExecutionDetail>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/executions/${encodeURIComponent(executionId)}`,
  );
}

export function listToolInvocations(
  agentId: string,
  executionId: string,
  params: AgentHistoryPageParams = {},
) {
  return apiGet<ToolInvocationListResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/executions/${encodeURIComponent(executionId)}/tool-invocations${historyQuery(params)}`,
  );
}
