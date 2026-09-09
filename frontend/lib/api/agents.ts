import { apiGet } from "@/lib/api/client";
import type {
  Agent,
  AgentListResponse,
  AgentStatus,
  AgentType,
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
