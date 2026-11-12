import { apiPost } from "@/lib/api/client";
import type { VerificationEmailResponse, VerifyEmailResponse } from "@/types/api";

export function requestVerificationEmail(email: string) {
  return apiPost<VerificationEmailResponse>("/api/v1/auth/verification-email", {
    email,
  });
}

export function verifyEmail(token: string) {
  return apiPost<VerifyEmailResponse>(
    "/api/v1/auth/verify-email",
    { token },
    { token: null },
  );
}
