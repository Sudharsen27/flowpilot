import { apiGet } from "@/lib/api/client";
import type {
  ActivityEntityType,
  ActivityEvent,
  ActivityEventType,
  ActivityListParams,
  ActivityListResponse,
} from "@/types/api";

function listQuery(params: ActivityListParams = {}) {
  const query = new URLSearchParams();
  if (params.type) {
    query.set("type", params.type);
  }
  if (params.entity_type) {
    query.set("entity_type", params.entity_type);
  }
  if (params.entity_id?.trim()) {
    query.set("entity_id", params.entity_id.trim());
  }
  if (params.q?.trim()) {
    query.set("q", params.q.trim());
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

export function listActivity(params: ActivityListParams = {}) {
  return apiGet<ActivityListResponse>(`/api/v1/activity${listQuery(params)}`);
}

export function getActivity(activityId: string) {
  return apiGet<ActivityEvent>(
    `/api/v1/activity/${encodeURIComponent(activityId)}`,
  );
}

export type { ActivityEntityType, ActivityEventType };
