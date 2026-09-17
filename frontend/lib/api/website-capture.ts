import { apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  WebsiteCaptureSettings,
  WebsiteCaptureSettingsUpdate,
} from "@/types/api";

export type { WebsiteCaptureSettings, WebsiteCaptureSettingsUpdate };

export type PublicCaptureForm = {
  organization_name: string;
};

export type PublicEnquiryCreateRequest = {
  name: string;
  email: string;
  company?: string | null;
  enquiry: string;
  website?: string | null;
};

export function getPublicEnquiryForm(slug: string) {
  return apiGet<PublicCaptureForm>(
    `/api/v1/public/organizations/${encodeURIComponent(slug)}/enquiries`,
    { token: null },
  );
}

export function submitPublicEnquiry(slug: string, input: PublicEnquiryCreateRequest) {
  return apiPost<void>(
    `/api/v1/public/organizations/${encodeURIComponent(slug)}/enquiries`,
    input,
    { token: null },
  );
}

export function getWebsiteCaptureSettings() {
  return apiGet<WebsiteCaptureSettings>(
    "/api/v1/organizations/current/website-capture",
  );
}

export function updateWebsiteCaptureSettings(
  input: WebsiteCaptureSettingsUpdate,
) {
  return apiPatch<WebsiteCaptureSettings>(
    "/api/v1/organizations/current/website-capture",
    {
      website_capture_enabled: input.website_capture_enabled,
      sales_agent_auto_start_enabled: input.sales_agent_auto_start_enabled,
      default_sales_agent_id: input.default_sales_agent_id,
    },
  );
}
