import { ApiError, apiGet, apiPatch, apiPost } from "@/lib/api/client";
import type {
  Deal,
  DealCreateRequest,
  DealHistoryResponse,
  DealListResponse,
  DealStage,
  DealStageChangeRequest,
  DealUpdateRequest,
} from "@/types/api";

export type DealListParams = {
  stage?: DealStage;
  ownerUserId?: string;
  closeDateFrom?: string;
  closeDateTo?: string;
  q?: string;
  limit?: number;
  offset?: number;
};

function clampedPage(params: { limit?: number; offset?: number }, query: URLSearchParams) {
  if (params.limit !== undefined) {
    const limit = Math.min(100, Math.max(1, Math.trunc(params.limit)));
    query.set("limit", String(Number.isFinite(limit) ? limit : 20));
  }
  if (params.offset !== undefined) {
    const offset = Math.max(0, Math.trunc(params.offset));
    query.set("offset", String(Number.isFinite(offset) ? offset : 0));
  }
}

export function listDeals(params: DealListParams = {}) {
  const query = new URLSearchParams();
  if (params.stage) query.set("stage", params.stage);
  if (params.ownerUserId) query.set("owner_user_id", params.ownerUserId);
  if (params.closeDateFrom) query.set("close_date_from", params.closeDateFrom);
  if (params.closeDateTo) query.set("close_date_to", params.closeDateTo);
  const search = params.q?.trim();
  if (search) query.set("q", search.slice(0, 200));
  clampedPage(params, query);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiGet<DealListResponse>(`/api/v1/deals${suffix}`);
}

export function getDeal(dealId: string) {
  return apiGet<Deal>(`/api/v1/deals/${encodeURIComponent(dealId)}`);
}

export function createDeal(input: DealCreateRequest) {
  return apiPost<Deal>("/api/v1/deals", input);
}

export function updateDeal(dealId: string, input: DealUpdateRequest) {
  return apiPatch<Deal>(`/api/v1/deals/${encodeURIComponent(dealId)}`, input);
}

export function changeDealStage(dealId: string, input: DealStageChangeRequest) {
  return apiPost<Deal>(`/api/v1/deals/${encodeURIComponent(dealId)}/stage`, input);
}

export function getDealHistory(dealId: string, params: { limit?: number; offset?: number } = {}) {
  const query = new URLSearchParams();
  if (params.limit !== undefined) {
    query.set("limit", String(Math.min(200, Math.max(1, Math.trunc(params.limit)))));
  }
  if (params.offset !== undefined) {
    query.set("offset", String(Math.max(0, Math.trunc(params.offset))));
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiGet<DealHistoryResponse>(
    `/api/v1/deals/${encodeURIComponent(dealId)}/history${suffix}`,
  );
}

/** True when the API rejected a write because the deal changed since it was loaded. */
export function isRevisionConflict(cause: unknown): cause is ApiError {
  return cause instanceof ApiError && cause.status === 409;
}

/** Field name → message from a FastAPI 422 body; "form" holds non-field errors. */
export function validationErrors(cause: unknown): Record<string, string> {
  if (!(cause instanceof ApiError) || cause.status !== 422) return {};
  const body = cause.body as { detail?: unknown } | null;
  if (typeof body?.detail === "string") return { form: body.detail };
  if (!Array.isArray(body?.detail)) return {};
  const errors: Record<string, string> = {};
  for (const item of body.detail as { loc?: unknown[]; msg?: unknown }[]) {
    const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : undefined;
    const key = typeof field === "string" && field !== "body" ? field : "form";
    if (typeof item.msg === "string" && !errors[key]) {
      errors[key] = item.msg.replace(/^Value error, /, "");
    }
  }
  return errors;
}
