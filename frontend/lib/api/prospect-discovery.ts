import { apiPostFile } from "@/lib/api/client";
import type { ProspectPreviewResponse } from "@/types/api";

export function previewProspectCsv(file: File) {
  return apiPostFile<ProspectPreviewResponse>(
    "/api/v1/prospect-discovery/preview",
    file,
    "text/csv",
  );
}