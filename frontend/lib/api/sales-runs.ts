import { ApiError, apiGet, apiPost } from "@/lib/api/client";
import type {
  SalesRun,
  SalesRunCancelRequest,
  SalesRunListParams,
  SalesRunListResponse,
  SalesRunStartRequest,
} from "@/types/api";

function listQuery(params: SalesRunListParams = {}) {
  const query = new URLSearchParams();
  if (params.status) {
    query.set("status", params.status);
  }
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function recoverFailedSalesRun(cause: unknown): SalesRun | null {
  if (!(cause instanceof ApiError)) return null;
  if (cause.status !== 502 && cause.status !== 503) return null;
  if (!isRecord(cause.body)) return null;
  if (typeof cause.body.id !== "string") return null;
  if (cause.body.status !== "FAILED") return null;
  if (typeof cause.body.agent_id !== "string") return null;
  if (typeof cause.body.lead_id !== "string") return null;
  return cause.body as unknown as SalesRun;
}

export async function startSalesRun(
  agentId: string,
  input: SalesRunStartRequest,
) {
  try {
    return await apiPost<SalesRun>(
      `/api/v1/agents/${encodeURIComponent(agentId)}/sales-runs`,
      input,
    );
  } catch (cause) {
    const recovered = recoverFailedSalesRun(cause);
    if (recovered) return recovered;
    throw cause;
  }
}

export function listSalesRuns(agentId: string, params: SalesRunListParams = {}) {
  return apiGet<SalesRunListResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/sales-runs${listQuery(params)}`,
  );
}

export function getSalesRun(agentId: string, salesRunId: string) {
  return apiGet<SalesRun>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/sales-runs/${encodeURIComponent(salesRunId)}`,
  );
}

export function cancelSalesRun(
  agentId: string,
  salesRunId: string,
  input: SalesRunCancelRequest,
) {
  return apiPost<SalesRun>(
    `/api/v1/agents/${encodeURIComponent(agentId)}/sales-runs/${encodeURIComponent(salesRunId)}/cancel`,
    input,
  );
}

export function listLeadSalesRuns(
  leadId: string,
  params: SalesRunListParams = {},
) {
  return apiGet<SalesRunListResponse>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/sales-runs${listQuery(params)}`,
  );
}

export function listOrganizationSalesRuns(
  params: SalesRunListParams = {},
) {
  return apiGet<SalesRunListResponse>(`/api/v1/sales-runs${listQuery(params)}`);
}
