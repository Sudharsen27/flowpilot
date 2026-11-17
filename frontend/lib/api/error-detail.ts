import { ApiError } from "@/lib/api/client";

export function apiErrorDetail(error: unknown, fallback: string): string {
  if (!(error instanceof ApiError) || !error.body || typeof error.body !== "object") {
    return fallback;
  }
  const detail = "detail" in error.body ? error.body.detail : null;
  return typeof detail === "string" && detail.trim() ? detail : fallback;
}
