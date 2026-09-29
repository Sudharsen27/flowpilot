import { apiGet } from "@/lib/api/client";
import { listActivity } from "@/lib/api/activity";
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
  if (params.human_attention_required !== undefined) {
    query.set("human_attention_required", String(params.human_attention_required));
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
  ).then(async (conversation) => {
    let activityItems;
    try {
      activityItems = await listActivity({
        type: "AI_ACTION",
        entity_type: "LEAD",
        lead_id: leadId,
        q: "Human attention required",
        limit: 50,
      });
    } catch {
      return conversation;
    }

    const existingActivityIds = new Set(
      conversation.items.map((item) => item.activity_id ?? item.id),
    );
    const attentionEvents = activityItems.items
      .filter(
        (event) =>
          event.type === "AI_ACTION" &&
          event.entity_type === "LEAD" &&
          event.lead_id === leadId &&
          event.title === "Human attention required" &&
          !existingActivityIds.has(event.id),
      )
      .map((event) => ({
        id: event.id,
        kind: "HUMAN_ATTENTION_REQUIRED" as const,
        direction: "internal" as const,
        occurred_at: event.occurred_at,
        title: event.title,
        summary: event.summary,
        body: null,
        status: event.status,
        actor_type: event.actor_type,
        actor_user_id: event.actor_user_id,
        agent_id: event.agent_id,
        source_entity_type: "LEAD" as const,
        source_entity_id: event.entity_id,
        activity_id: event.id,
        is_draft: false,
        is_sent_message: false,
      }));
    const items = [...conversation.items, ...attentionEvents].sort(
      (left, right) =>
        left.occurred_at.localeCompare(right.occurred_at) ||
        left.id.localeCompare(right.id),
    );
    return { ...conversation, items, total_items: items.length };
  });
}
