import type {
  InboxConversationState,
  LeadSource,
} from "@/types/api";

export type NeedsApprovalFilter = "" | "true" | "false";

export type InboxUrlState = {
  q: string;
  conversationState: InboxConversationState | "";
  source: LeadSource | "";
  needsApproval: NeedsApprovalFilter;
  offset: number;
  leadId: string | null;
};

export const INBOX_PAGE_SIZE = 20;

const CONVERSATION_STATES = new Set<InboxConversationState>([
  "OPEN",
  "NEEDS_APPROVAL",
  "CLOSED",
]);

const LEAD_SOURCES = new Set<LeadSource>([
  "MANUAL",
  "WEBSITE",
  "EMAIL",
  "CHAT",
  "API",
  "IMPORT",
]);

export function parseInboxSearchParams(
  searchParams: URLSearchParams,
): InboxUrlState {
  const conversationStateRaw = searchParams.get("state") ?? "";
  const sourceRaw = searchParams.get("source") ?? "";
  const needsRaw = searchParams.get("needs_approval") ?? "";
  const offsetRaw = Number.parseInt(searchParams.get("offset") ?? "0", 10);
  const leadRaw = searchParams.get("lead")?.trim() ?? "";

  return {
    q: searchParams.get("q")?.trim() ?? "",
    conversationState: CONVERSATION_STATES.has(
      conversationStateRaw as InboxConversationState,
    )
      ? (conversationStateRaw as InboxConversationState)
      : "",
    source: LEAD_SOURCES.has(sourceRaw as LeadSource)
      ? (sourceRaw as LeadSource)
      : "",
    needsApproval:
      needsRaw === "true" || needsRaw === "false"
        ? (needsRaw as NeedsApprovalFilter)
        : "",
    offset:
      Number.isFinite(offsetRaw) && offsetRaw > 0
        ? Math.max(0, Math.trunc(offsetRaw))
        : 0,
    leadId: leadRaw || null,
  };
}

export function serializeInboxSearchParams(state: InboxUrlState): string {
  const query = new URLSearchParams();
  if (state.q.trim()) query.set("q", state.q.trim());
  if (state.conversationState) query.set("state", state.conversationState);
  if (state.source) query.set("source", state.source);
  if (state.needsApproval) query.set("needs_approval", state.needsApproval);
  if (state.offset > 0) query.set("offset", String(state.offset));
  if (state.leadId) query.set("lead", state.leadId);
  return query.toString();
}

export function inboxUrlEquals(a: InboxUrlState, b: InboxUrlState): boolean {
  return (
    a.q === b.q &&
    a.conversationState === b.conversationState &&
    a.source === b.source &&
    a.needsApproval === b.needsApproval &&
    a.offset === b.offset &&
    a.leadId === b.leadId
  );
}
