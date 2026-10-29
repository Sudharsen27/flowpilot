import type { AgentExecutionStatus } from "@/types/api";

export type AgentExecutionsUrlState = {
  status: AgentExecutionStatus | null;
  agentId: string | null;
  leadId: string | null;
  limit: number;
  offset: number;
};

export const AGENT_EXECUTIONS_PATH = "/agents/executions";
export const AGENT_EXECUTIONS_PAGE_SIZE = 20;
/** Mirrors the backend `limit` bound on GET /api/v1/agent-executions. */
export const AGENT_EXECUTIONS_MAX_LIMIT = 50;
/** Mirrors the backend `max_length=36` bound on agent_id and lead_id. */
export const AGENT_EXECUTIONS_MAX_ID_LENGTH = 36;

export const AGENT_EXECUTION_STATUSES: readonly AgentExecutionStatus[] = [
  "QUEUED",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
];

const STATUSES = new Set<string>(AGENT_EXECUTION_STATUSES);

function parseId(raw: string | null): string | null {
  const value = raw?.trim() ?? "";
  if (!value || value.length > AGENT_EXECUTIONS_MAX_ID_LENGTH) return null;
  return value;
}

function parseNonNegativeInt(raw: string | null): number | null {
  if (raw === null || !/^\d+$/.test(raw.trim())) return null;
  const value = Number.parseInt(raw, 10);
  return Number.isSafeInteger(value) ? value : null;
}

/**
 * Invalid values fall back to defaults so the list request never fails
 * backend validation (unknown status, oversized IDs, out-of-range paging).
 */
export function parseAgentExecutionsSearchParams(
  searchParams: URLSearchParams,
): AgentExecutionsUrlState {
  const statusRaw = searchParams.get("status")?.trim().toUpperCase() ?? "";
  const limitRaw = parseNonNegativeInt(searchParams.get("limit"));
  const offsetRaw = parseNonNegativeInt(searchParams.get("offset"));

  return {
    status: STATUSES.has(statusRaw) ? (statusRaw as AgentExecutionStatus) : null,
    agentId: parseId(searchParams.get("agent_id")),
    leadId: parseId(searchParams.get("lead_id")),
    limit:
      limitRaw !== null && limitRaw >= 1
        ? Math.min(limitRaw, AGENT_EXECUTIONS_MAX_LIMIT)
        : AGENT_EXECUTIONS_PAGE_SIZE,
    offset: offsetRaw ?? 0,
  };
}

export function serializeAgentExecutionsSearchParams(
  state: AgentExecutionsUrlState,
): string {
  const query = new URLSearchParams();
  if (state.status) query.set("status", state.status);
  const agentId = parseId(state.agentId);
  if (agentId) query.set("agent_id", agentId);
  const leadId = parseId(state.leadId);
  if (leadId) query.set("lead_id", leadId);
  if (state.limit !== AGENT_EXECUTIONS_PAGE_SIZE) {
    query.set("limit", String(state.limit));
  }
  if (state.offset > 0) query.set("offset", String(state.offset));
  return query.toString();
}

export function agentExecutionsUrlEquals(
  a: AgentExecutionsUrlState,
  b: AgentExecutionsUrlState,
): boolean {
  return (
    a.status === b.status &&
    a.agentId === b.agentId &&
    a.leadId === b.leadId &&
    a.limit === b.limit &&
    a.offset === b.offset
  );
}

/** Build an organization execution history href, e.g. from agent or lead pages. */
export function buildAgentExecutionsHref(
  options: {
    status?: AgentExecutionStatus | null;
    agentId?: string | null;
    leadId?: string | null;
  } = {},
): string {
  const query = serializeAgentExecutionsSearchParams({
    status: options.status ?? null,
    agentId: options.agentId ?? null,
    leadId: options.leadId ?? null,
    limit: AGENT_EXECUTIONS_PAGE_SIZE,
    offset: 0,
  });
  return query ? `${AGENT_EXECUTIONS_PATH}?${query}` : AGENT_EXECUTIONS_PATH;
}
