import { apiGet } from "@/lib/api/client";

export type CrmCompanySummary = {
  id: string;
  name: string;
  website_domain: string | null;
  archived_at: string | null;
};

export function getCrmCompany(
  companyId: string,
  options: { signal?: AbortSignal } = {},
) {
  return apiGet<CrmCompanySummary>(
    `/api/v1/companies/${encodeURIComponent(companyId)}`,
    options,
  );
}
