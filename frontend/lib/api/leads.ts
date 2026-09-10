import { apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  Lead,
  LeadCreateRequest,
  LeadListResponse,
  LeadSource,
  LeadStatus,
  LeadUpdateRequest,
} from "@/types/api";

export type LeadListParams = {
  status?: LeadStatus;
  source?: LeadSource;
  q?: string;
  limit?: number;
  offset?: number;
};

function listQuery(params: LeadListParams = {}) {
  const query = new URLSearchParams();
  if (params.status) {
    query.set("status", params.status);
  }
  if (params.source) {
    query.set("source", params.source);
  }
  if (params.q?.trim()) {
    query.set("q", params.q.trim());
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

export function getLeads(params: LeadListParams = {}) {
  return apiGet<LeadListResponse>(`/api/v1/leads${listQuery(params)}`);
}

export function getLead(leadId: string) {
  return apiGet<Lead>(`/api/v1/leads/${encodeURIComponent(leadId)}`);
}

export function createLead(input: LeadCreateRequest) {
  return apiPost<Lead>("/api/v1/leads", input);
}

export function updateLead(leadId: string, input: LeadUpdateRequest) {
  return apiPatch<Lead>(
    `/api/v1/leads/${encodeURIComponent(leadId)}`,
    input,
  );
}
