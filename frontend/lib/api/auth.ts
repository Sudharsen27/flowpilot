import { apiPost } from "@/lib/api/client";
import type {
  PasswordResetConfirmResponse,
  PasswordResetResponse,
  VerificationEmailResponse,
  VerifyEmailResponse,
} from "@/types/api";

export function logoutSession() {
  return apiPost<void>("/api/v1/auth/logout", undefined, {
    credentials: "include",
    headers: { "X-FlowPilot-Request": "1" },
  });
}

export function requestVerificationEmail(email: string) {
  return apiPost<VerificationEmailResponse>("/api/v1/auth/verification-email", {
    email,
  });
}

export function requestPasswordReset(email: string) {
  return apiPost<PasswordResetResponse>("/api/v1/auth/password-reset", {
    email,
  });
}

export function confirmPasswordReset(token: string, password: string) {
  return apiPost<PasswordResetConfirmResponse>(
    "/api/v1/auth/password-reset/confirm",
    { token, password },
    { token: null },
  );
}

export function verifyEmail(token: string) {
  return apiPost<VerifyEmailResponse>(
    "/api/v1/auth/verify-email",
    { token },
    { token: null },
  );
}
