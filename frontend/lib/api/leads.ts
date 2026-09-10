import { apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  Lead,
  LeadCreateRequest,
  LeadListResponse,
  LeadQualificationResult,
  LeadQualifyRequest,
  LeadRespondRequest,
  LeadResponseDraftApproveRequest,
  LeadResponseDraftRejectRequest,
  LeadResponseDraftResult,
  LeadResponseDraftUpdateRequest,
  LeadEmailSendResult,
  LeadFollowUp,
  LeadFollowUpCreateRequest,
  LeadFollowUpLifecycleRequest,
  LeadFollowUpListResponse,
  LeadFollowUpStatus,
  LeadFollowUpUpdateRequest,
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

export function qualifyLead(leadId: string, input: LeadQualifyRequest) {
  return apiPost<LeadQualificationResult>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/qualify`,
    input,
  );
}

export function generateLeadResponseDraft(
  leadId: string,
  input: LeadRespondRequest,
) {
  return apiPost<LeadResponseDraftResult>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/respond`,
    input,
  );
}

export function getLeadResponseDraft(leadId: string, draftId: string) {
  return apiGet<LeadResponseDraftResult>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/response-drafts/${encodeURIComponent(draftId)}`,
  );
}

export function updateLeadResponseDraft(
  leadId: string,
  draftId: string,
  input: LeadResponseDraftUpdateRequest,
) {
  return apiPatch<LeadResponseDraftResult>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/response-drafts/${encodeURIComponent(draftId)}`,
    input,
  );
}

export function approveLeadResponseDraft(
  leadId: string,
  draftId: string,
  input: LeadResponseDraftApproveRequest,
) {
  return apiPost<LeadResponseDraftResult>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/response-drafts/${encodeURIComponent(draftId)}/approve`,
    input,
  );
}

export function rejectLeadResponseDraft(
  leadId: string,
  draftId: string,
  input: LeadResponseDraftRejectRequest,
) {
  return apiPost<LeadResponseDraftResult>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/response-drafts/${encodeURIComponent(draftId)}/reject`,
    input,
  );
}

export function sendLeadResponseDraft(leadId: string, draftId: string) {
  return apiPost<LeadEmailSendResult>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/response-drafts/${encodeURIComponent(draftId)}/send`,
    {},
  );
}

export type LeadFollowUpListParams = {
  status?: LeadFollowUpStatus;
  overdue?: boolean;
  limit?: number;
  offset?: number;
};

function followUpListQuery(params: LeadFollowUpListParams = {}) {
  const query = new URLSearchParams();
  if (params.status) {
    query.set("status", params.status);
  }
  if (params.overdue !== undefined) {
    query.set("overdue", String(params.overdue));
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

export function getLeadFollowUps(leadId: string, params: LeadFollowUpListParams = {}) {
  return apiGet<LeadFollowUpListResponse>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/follow-ups${followUpListQuery(params)}`,
  );
}

export function getLeadFollowUp(leadId: string, followUpId: string) {
  return apiGet<LeadFollowUp>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/follow-ups/${encodeURIComponent(followUpId)}`,
  );
}

export function createLeadFollowUp(leadId: string, input: LeadFollowUpCreateRequest) {
  return apiPost<LeadFollowUp>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/follow-ups`,
    input,
  );
}

export function updateLeadFollowUp(
  leadId: string,
  followUpId: string,
  input: LeadFollowUpUpdateRequest,
) {
  return apiPatch<LeadFollowUp>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/follow-ups/${encodeURIComponent(followUpId)}`,
    input,
  );
}

export function completeLeadFollowUp(
  leadId: string,
  followUpId: string,
  input: LeadFollowUpLifecycleRequest,
) {
  return apiPost<LeadFollowUp>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/follow-ups/${encodeURIComponent(followUpId)}/complete`,
    input,
  );
}

export function cancelLeadFollowUp(
  leadId: string,
  followUpId: string,
  input: LeadFollowUpLifecycleRequest,
) {
  return apiPost<LeadFollowUp>(
    `/api/v1/leads/${encodeURIComponent(leadId)}/follow-ups/${encodeURIComponent(followUpId)}/cancel`,
    input,
  );
}
