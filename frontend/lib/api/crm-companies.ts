import { apiGet } from "@/lib/api/client";

export type CrmCompanySummary = {
  id: string;
  name: string;
  website_domain: string | null;
  archived_at: string | null;
};

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
  lifecycle_status: "PROSPECT" | "CUSTOMER" | "FORMER_CUSTOMER" | "PARTNER";
  source: "MANUAL" | "IMPORT" | "LEAD_CONVERSION" | "COMPANY_PROSPECT" | "API";
  owner_user_id: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
};

export function getCrmCompany(
  companyId: string,
  options: { signal?: AbortSignal } = {},
) {
  return apiGet<CrmCompanyDetail>(
    `/api/v1/companies/${encodeURIComponent(companyId)}`,
    options,
  );
}
