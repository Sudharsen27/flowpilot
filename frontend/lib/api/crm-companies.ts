import { apiGet, apiPatch, apiPost } from "@/lib/api/client";

export type CrmCompanySummary = {
  id: string;
  name: string;
  website_domain: string | null;
  archived_at: string | null;
};

export type CrmCompanyLifecycleStatus =
  "PROSPECT" | "CUSTOMER" | "FORMER_CUSTOMER" | "PARTNER";

export type CrmCompanyDetail = CrmCompanySummary & {
  industry: string | null;
  employee_count: number | null;
  phone: string | null;
  email: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  region: string | null;
  postal_code: string | null;
  country: string | null;
  description: string | null;
  lifecycle_status: CrmCompanyLifecycleStatus;
  source: "MANUAL" | "IMPORT" | "LEAD_CONVERSION" | "COMPANY_PROSPECT" | "API";
  owner_user_id: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
};

export type CrmCompanyListResponse = {
  items: CrmCompanyDetail[];
  limit: number;
  offset: number;
  total: number;
};

export type CrmCompanyListParams = {
  q?: string;
  lifecycleStatus?: CrmCompanyLifecycleStatus;
  ownerUserId?: string;
  includeArchived?: boolean;
  limit?: number;
  offset?: number;
};

export type CrmCompanyCreateRequest = {
  name: string;
  website_domain?: string | null;
  industry?: string | null;
  employee_count?: number | null;
  phone?: string | null;
  email?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  region?: string | null;
  postal_code?: string | null;
  country?: string | null;
  description?: string | null;
  lifecycle_status?: CrmCompanyLifecycleStatus;
  owner_user_id?: string | null;
};

export type CrmCompanyUpdateRequest = Partial<CrmCompanyCreateRequest> & {
  expected_revision: number;
};

function listQuery(params: CrmCompanyListParams = {}) {
  const query = new URLSearchParams();
  if (params.q?.trim()) {
    query.set("q", params.q.trim());
  }
  if (params.lifecycleStatus) {
    query.set("lifecycle_status", params.lifecycleStatus);
  }
  if (params.ownerUserId) {
    query.set("owner_user_id", params.ownerUserId);
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

export function listCrmCompanies(
  params: CrmCompanyListParams = {},
  options: { signal?: AbortSignal } = {},
) {
  return apiGet<CrmCompanyListResponse>(
    `/api/v1/companies${listQuery(params)}`,
    options,
  );
}

export function getCrmCompany(
  companyId: string,
  options: { signal?: AbortSignal } = {},
) {
  return apiGet<CrmCompanyDetail>(
    `/api/v1/companies/${encodeURIComponent(companyId)}`,
    options,
  );
}

export function createCrmCompany(input: CrmCompanyCreateRequest) {
  return apiPost<CrmCompanyDetail>("/api/v1/companies", input);
}

export function updateCrmCompany(
  companyId: string,
  input: CrmCompanyUpdateRequest,
) {
  return apiPatch<CrmCompanyDetail>(
    `/api/v1/companies/${encodeURIComponent(companyId)}`,
    input,
  );
}

export function archiveCrmCompany(companyId: string, expectedRevision: number) {
  return apiPost<CrmCompanyDetail>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/archive`,
    { expected_revision: expectedRevision },
  );
}

export function restoreCrmCompany(companyId: string, expectedRevision: number) {
  return apiPost<CrmCompanyDetail>(
    `/api/v1/companies/${encodeURIComponent(companyId)}/restore`,
    { expected_revision: expectedRevision },
  );
}
