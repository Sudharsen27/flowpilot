import { apiPostFile } from "@/lib/api/client";
import type { ProspectImportResponse, ProspectPreviewResponse } from "@/types/api";

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
