import { apiGet } from "@/lib/api/client";
import type {
  InboxConversationResponse,
  InboxListParams,
  InboxListResponse,
} from "@/types/api";

function listQuery(params: InboxListParams = {}) {
  const query = new URLSearchParams();
  if (params.q?.trim()) {
    query.set("q", params.q.trim());
  }
  if (params.lead_status) {
    query.set("lead_status", params.lead_status);
  }
  if (params.needs_approval !== undefined) {
    query.set("needs_approval", String(params.needs_approval));
  }
  if (params.conversation_state) {
    query.set("conversation_state", params.conversation_state);
  }
  if (params.email_status) {
    query.set("email_status", params.email_status);
  }
  if (params.sales_run_status) {
    query.set("sales_run_status", params.sales_run_status);
  }
  if (params.follow_up_status) {
    query.set("follow_up_status", params.follow_up_status);
  }
  if (params.source) {
    query.set("source", params.source);
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

export function getInbox(params: InboxListParams = {}) {
  return apiGet<InboxListResponse>(`/api/v1/inbox${listQuery(params)}`);
}

export function getInboxConversation(leadId: string) {
  return apiGet<InboxConversationResponse>(
    `/api/v1/inbox/${encodeURIComponent(leadId)}`,
  );
}
