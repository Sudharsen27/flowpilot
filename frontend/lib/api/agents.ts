import { apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  Agent,
  AgentCreateRequest,
  AgentExecutionRequest,
  AgentExecutionResult,
  AgentListResponse,
  AgentStatus,
  AgentType,
  AgentUpdateRequest,
} from "@/types/api";

export type AgentListFilters = {
  status?: AgentStatus;
  agentType?: AgentType;
};

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
