import { apiGet, apiPatch, apiPost } from "@/lib/api/client";

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

export type WebsiteCaptureSettings = {
  website_capture_enabled: boolean;
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

export function updateWebsiteCaptureSettings(enabled: boolean) {
  return apiPatch<WebsiteCaptureSettings>(
    "/api/v1/organizations/current/website-capture",
    { website_capture_enabled: enabled },
  );
}
