import { apiPost, apiPostFile } from "@/lib/api/client";
import type {
  ProspectDiscoverySearchRequest,
  ProspectDiscoverySearchResponse,
  ProspectImportResponse,
  ProspectPreviewResponse,
} from "@/types/api";

export function searchProspects(input: ProspectDiscoverySearchRequest) {
  return apiPost<ProspectDiscoverySearchResponse>(
    "/api/v1/prospect-discovery/search",
    input,
  );
}

export function previewProspectCsv(file: File) {
  return apiPostFile<ProspectPreviewResponse>(
    "/api/v1/prospect-discovery/preview",
    file,
    "text/csv",
  );
}

export function importProspectCsv(file: File) {
  return apiPostFile<ProspectImportResponse>(
    "/api/v1/prospect-discovery/import",
    file,
    "text/csv",
    { "X-Prospect-Import-Confirmed": "true" },
  );
}
