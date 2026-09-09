import { apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  Agent,
  AgentCreateRequest,
  AgentExecutionDetail,
  AgentExecutionListResponse,
  AgentExecutionRequest,
  AgentExecutionResult,
  AgentListResponse,
  AgentStatus,
  AgentType,
  AgentUpdateRequest,
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

export function executeAgent(agentId: string, input: AgentExecutionRequest) {
  return apiPost<AgentExecutionResult>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/execute`,
    input,
  );
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
