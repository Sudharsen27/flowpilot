import { apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  CompanyProspect,
  CompanyProspectListResponse,
  CompanyProspectStatus,
  EvidenceQuality,
} from "@/types/api";

export type CompanyProspectListParams = {
  status?: CompanyProspectStatus;
  q?: string;
  limit?: number;
  offset?: number;
};

export type CompanyProspectCreateInput = {
  name: string;
  website_domain?: string | null;
  name_evidence_quality?: EvidenceQuality;
  website_domain_evidence_quality?: EvidenceQuality;
};

function listQuery(params: CompanyProspectListParams = {}) {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  const search = params.q?.trim();
  if (search) query.set("q", search.slice(0, 200));
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

export function getCompanyProspects(params: CompanyProspectListParams = {}) {
  return apiGet<CompanyProspectListResponse>(
    `/api/v1/company-prospects${listQuery(params)}`,
  );
}

export function getCompanyProspect(prospectId: string) {
  return apiGet<CompanyProspect>(
    `/api/v1/company-prospects/${encodeURIComponent(prospectId)}`,
  );
}

export function createCompanyProspect(input: CompanyProspectCreateInput) {
  return apiPost<CompanyProspect>("/api/v1/company-prospects", input);
}

export function updateCompanyProspectLifecycle(
  prospectId: string,
  status: CompanyProspectStatus,
) {
  return apiPatch<CompanyProspect>(
    `/api/v1/company-prospects/${encodeURIComponent(prospectId)}/lifecycle`,
    { status },
  );
}
