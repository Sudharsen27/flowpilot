import { apiGet } from "@/lib/api/client";
import type { ApprovalListParams, ApprovalListResponse } from "@/types/api";

function listQuery(params: ApprovalListParams = {}) {
  const query = new URLSearchParams();
  if (params.q?.trim()) {
    query.set("q", params.q.trim());
  }
  if (params.status) {
    query.set("status", params.status);
  }
  if (params.limit !== undefined) {
    const limit = Math.min(50, Math.max(1, Math.trunc(params.limit)));
    query.set("limit", String(Number.isFinite(limit) ? limit : 20));
  }
  if (params.offset !== undefined) {
    const offset = Math.max(0, Math.trunc(params.offset));
    query.set("offset", String(Number.isFinite(offset) ? offset : 0));
  }
  return query.size > 0 ? `?${query.toString()}` : "";
}

export function getApprovals(params: ApprovalListParams = {}) {
  return apiGet<ApprovalListResponse>(`/api/v1/approvals${listQuery(params)}`);
}
