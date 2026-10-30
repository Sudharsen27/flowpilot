import { apiGet, apiPut } from "@/lib/api/client";
import { notifySalesTargetsChanged } from "@/lib/deal-events";
import type {
  SalesTarget,
  SalesTargetListResponse,
  SalesTargetUpsertRequest,
} from "@/types/api";

export type SalesTargetListParams = {
  ownerUserId?: string;
  organizationOnly?: boolean;
  periodFrom?: string;
  periodTo?: string;
  limit?: number;
  offset?: number;
};

export function listSalesTargets(params: SalesTargetListParams = {}) {
  const query = new URLSearchParams();
  if (params.ownerUserId) query.set("owner_user_id", params.ownerUserId);
  if (params.organizationOnly) query.set("organization_only", "true");
  if (params.periodFrom) query.set("period_from", params.periodFrom);
  if (params.periodTo) query.set("period_to", params.periodTo);
  if (params.limit !== undefined) {
    query.set("limit", String(Math.min(200, Math.max(1, Math.trunc(params.limit)))));
  }
  if (params.offset !== undefined) {
    query.set("offset", String(Math.max(0, Math.trunc(params.offset))));
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiGet<SalesTargetListResponse>(`/api/v1/sales-targets${suffix}`);
}

/**
 * Creates or replaces the target for one calendar month (OWNER/ADMIN only). The cached
 * forecast is refreshed afterwards, even after a failure that may still have saved.
 */
export function upsertSalesTarget(input: SalesTargetUpsertRequest) {
  return apiPut<SalesTarget>("/api/v1/sales-targets", input).finally(notifySalesTargetsChanged);
}
