import type { StatusValue } from "@/components/ui/status-badge";

/**
 * Canonical domain codes mapped onto one StatusBadge semantic language.
 * Display labels stay in domain wrappers. OVERDUE is derived UI state.
 */
export const CANONICAL_STATUS_SEMANTICS = {
  COMPLETED: "success",
  SENT: "success",
  APPROVED: "success",
  ACTIVE: "success",
  QUALIFIED: "success",
  PENDING: "pending",
  QUEUED: "pending",
  RUNNING: "pending",
  READY: "pending",
  GENERATED: "pending",
  NEW: "pending",
  FAILED: "failed",
  PAUSED: "paused",
  CANCELLED: "paused",
  DRAFT: "draft",
  EDITED: "draft",
  NEEDS_ATTENTION: "warning",
  REJECTED: "warning",
  AWAITING_APPROVAL: "warning",
  OVERDUE: "high",
} as const satisfies Record<string, StatusValue>;

export type CanonicalStatusCode = keyof typeof CANONICAL_STATUS_SEMANTICS;

export function normalizeStatusCode(code: string): string {
  return code.trim().replace(/[-\s]+/g, "_").toUpperCase();
}

export function semanticStatus(code: string): StatusValue | undefined {
  const normalized = normalizeStatusCode(code);
  if (normalized in CANONICAL_STATUS_SEMANTICS) {
    return CANONICAL_STATUS_SEMANTICS[normalized as CanonicalStatusCode];
  }
  return undefined;
}

export function semanticStatusOr(
  code: string,
  fallback: StatusValue,
): StatusValue {
  return semanticStatus(code) ?? fallback;
}

export function statusPresentation(
  code: string,
  label: string,
  fallback: StatusValue = "draft",
): { status: StatusValue; label: string } {
  return { status: semanticStatusOr(code, fallback), label };
}
