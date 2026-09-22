import type { ApprovalQueueStatus } from "@/types/api";

export type ApprovalsUrlState = {
  q: string;
  status: ApprovalQueueStatus;
  offset: number;
  approvalId: string | null;
};

export const APPROVALS_PAGE_SIZE = 20;

const STATUSES = new Set<ApprovalQueueStatus>([
  "pending",
  "approved",
  "rejected",
]);

export function parseApprovalsSearchParams(
  searchParams: URLSearchParams,
): ApprovalsUrlState {
  const statusRaw = searchParams.get("status") ?? "pending";
  const offsetRaw = Number.parseInt(searchParams.get("offset") ?? "0", 10);
  const approvalRaw = searchParams.get("approval")?.trim() ?? "";

  return {
    q: searchParams.get("q")?.trim() ?? "",
    status: STATUSES.has(statusRaw as ApprovalQueueStatus)
      ? (statusRaw as ApprovalQueueStatus)
      : "pending",
    offset:
      Number.isFinite(offsetRaw) && offsetRaw > 0
        ? Math.max(0, Math.trunc(offsetRaw))
        : 0,
    approvalId: approvalRaw || null,
  };
}

export function serializeApprovalsSearchParams(
  state: ApprovalsUrlState,
): string {
  const query = new URLSearchParams();
  if (state.q.trim()) query.set("q", state.q.trim());
  if (state.status !== "pending") query.set("status", state.status);
  if (state.offset > 0) query.set("offset", String(state.offset));
  if (state.approvalId) query.set("approval", state.approvalId);
  return query.toString();
}

export function approvalsUrlEquals(
  a: ApprovalsUrlState,
  b: ApprovalsUrlState,
): boolean {
  return (
    a.q === b.q &&
    a.status === b.status &&
    a.offset === b.offset &&
    a.approvalId === b.approvalId
  );
}
