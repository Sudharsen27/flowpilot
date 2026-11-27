import { apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type { LeadSource, LeadStatus } from "@/types/api";

export type CrmContact = {
  id: string;
  display_name: string;
  first_name: string | null;
  last_name: string | null;
  job_title: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  linkedin_url: string | null;
  company_id: string | null;
  owner_user_id: string | null;
  source: "MANUAL" | "IMPORT" | "LEAD_CONVERSION" | "COMPANY_PROSPECT" | "API";
  status: "ACTIVE" | "INACTIVE";
  description: string | null;
  revision: number;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CrmContactListResponse = {
  items: CrmContact[];
  limit: number;
  offset: number;
  total: number;
};

export type CrmContactListParams = {
  q?: string;
  companyId?: string;
  status?: CrmContact["status"];
  ownerUserId?: string;
  leadId?: string;
  includeArchived?: boolean;
  limit?: number;
  offset?: number;
};

export type CrmContactCreateRequest = {
  display_name: string;
  first_name?: string | null;
  last_name?: string | null;
  job_title?: string | null;
  email?: string | null;
  phone?: string | null;
  mobile?: string | null;
  linkedin_url?: string | null;
  company_id?: string | null;
  owner_user_id?: string | null;
  status?: CrmContact["status"];
  description?: string | null;
};

export type CrmContactUpdateRequest = Partial<CrmContactCreateRequest> & {
  expected_revision: number;
};

export type CrmContactLeadSummary = {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  source: LeadSource;
  status: LeadStatus;
  created_at: string;
  updated_at: string;
};

export type CrmContactLeadListResponse = {
  items: CrmContactLeadSummary[];
  limit: number;
  offset: number;
  total: number;
};

export type CrmContactLeadListParams = {
  limit?: number;
  offset?: number;
};

export function getCrmContact(
  contactId: string,
  options: { signal?: AbortSignal } = {},
) {
  return apiGet<CrmContact>(
    `/api/v1/contacts/${encodeURIComponent(contactId)}`,
    options,
  );
}

export function createCrmContact(input: CrmContactCreateRequest) {
  return apiPost<CrmContact>("/api/v1/contacts", input);
}

export function updateCrmContact(
  contactId: string,
  input: CrmContactUpdateRequest,
) {
  return apiPatch<CrmContact>(
    `/api/v1/contacts/${encodeURIComponent(contactId)}`,
    input,
  );
}

export function archiveCrmContact(contactId: string, expectedRevision: number) {
  return apiPost<CrmContact>(
    `/api/v1/contacts/${encodeURIComponent(contactId)}/archive`,
    { expected_revision: expectedRevision },
  );
}

export function restoreCrmContact(contactId: string, expectedRevision: number) {
  return apiPost<CrmContact>(
    `/api/v1/contacts/${encodeURIComponent(contactId)}/restore`,
    { expected_revision: expectedRevision },
  );
}

export type CrmContactLeadLinkRequest = {
  expected_revision: number;
  lead_id: string;
  linked: boolean;
};

export type CrmContactLeadLinkResponse = {
  contact_id: string;
  lead_id: string;
  linked: boolean;
  revision: number;
};

function listQuery(params: CrmContactListParams = {}) {
  const query = new URLSearchParams();
  if (params.q?.trim()) {
    query.set("q", params.q.trim());
  }
  if (params.companyId) {
    query.set("company_id", params.companyId);
  }
  if (params.status) {
    query.set("status", params.status);
  }
  if (params.ownerUserId) {
    query.set("owner_user_id", params.ownerUserId);
  }
  if (params.leadId) {
    query.set("lead_id", params.leadId);
  }
  if (params.includeArchived !== undefined) {
    query.set("include_archived", String(params.includeArchived));
  }
  if (params.limit !== undefined) {
    const limit = Math.min(100, Math.max(1, Math.trunc(params.limit)));
    query.set("limit", String(Number.isFinite(limit) ? limit : 20));
  }
  if (params.offset !== undefined) {
    const offset = Math.max(0, Math.trunc(params.offset));
    query.set("offset", String(Number.isFinite(offset) ? offset : 0));
  }
  return query.size > 0 ? `?${query.toString()}` : "";
}

export function listCrmContacts(
  params: CrmContactListParams = {},
  options: { signal?: AbortSignal } = {},
) {
  return apiGet<CrmContactListResponse>(
    `/api/v1/contacts${listQuery(params)}`,
    options,
  );
}

function contactLeadListQuery(params: CrmContactLeadListParams = {}) {
  const query = new URLSearchParams();
  if (params.limit !== undefined) {
    const limit = Math.min(100, Math.max(1, Math.trunc(params.limit)));
    query.set("limit", String(Number.isFinite(limit) ? limit : 20));
  }
  if (params.offset !== undefined) {
    const offset = Math.max(0, Math.trunc(params.offset));
    query.set("offset", String(Number.isFinite(offset) ? offset : 0));
  }
  return query.size > 0 ? `?${query.toString()}` : "";
}

export function listCrmContactLeads(
  contactId: string,
  params: CrmContactLeadListParams = {},
  options: { signal?: AbortSignal } = {},
) {
  return apiGet<CrmContactLeadListResponse>(
    `/api/v1/contacts/${encodeURIComponent(contactId)}/leads${contactLeadListQuery(params)}`,
    options,
  );
}

export function updateCrmContactLeadLink(
  contactId: string,
  input: CrmContactLeadLinkRequest,
) {
  return apiPatch<CrmContactLeadLinkResponse>(
    `/api/v1/contacts/${encodeURIComponent(contactId)}/leads`,
    input,
  );
}
