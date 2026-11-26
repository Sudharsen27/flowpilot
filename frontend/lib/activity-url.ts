import type { ActivityEntityType, ActivityEventType } from "@/types/api";

export type ActivityUrlState = {
  q: string;
  type: ActivityEventType | "";
  entityType: ActivityEntityType | "";
  offset: number;
  eventId: string | null;
};

export const ACTIVITY_PATH = "/activity";
export const ACTIVITY_PAGE_SIZE = 20;

const EVENT_TYPES = new Set<ActivityEventType>([
  "AI_ACTION",
  "APPROVAL",
  "HUMAN_ACTION",
  "SYSTEM_EVENT",
]);

const ENTITY_TYPES = new Set<ActivityEntityType>([
  "LEAD",
  "SALES_RUN",
  "LEAD_EMAIL_SEND",
  "AGENT_EXECUTION",
  "LEAD_FOLLOW_UP",
  "LEAD_FOLLOW_UP_EXECUTION",
  "LEAD_RESPONSE_DRAFT",
  "LEAD_QUALIFICATION",
  "KNOWLEDGE_ENTRY",
  "WORKFLOW_RULE",
  "WEBHOOK_ENDPOINT",
  "COMPANY_PROSPECT",
  "CONTACT",
  "COMPANY",
]);

function parseId(raw: string | null): string | null {
  const value = raw?.trim() ?? "";
  return value && value.length <= 36 ? value : null;
}

export function parseActivitySearchParams(
  searchParams: URLSearchParams,
): ActivityUrlState {
  const type = searchParams.get("type")?.trim().toUpperCase() ?? "";
  const entityType =
    searchParams.get("entity_type")?.trim().toUpperCase() ?? "";
  const offsetRaw = searchParams.get("offset")?.trim() ?? "";
  const offset = /^\d+$/.test(offsetRaw) ? Number.parseInt(offsetRaw, 10) : 0;
  return {
    q: (searchParams.get("q") ?? "").trim().slice(0, 200),
    type: EVENT_TYPES.has(type as ActivityEventType)
      ? (type as ActivityEventType)
      : "",
    entityType: ENTITY_TYPES.has(entityType as ActivityEntityType)
      ? (entityType as ActivityEntityType)
      : "",
    offset: Number.isSafeInteger(offset) ? offset : 0,
    eventId: parseId(searchParams.get("event")),
  };
}

export function serializeActivitySearchParams(state: ActivityUrlState): string {
  const query = new URLSearchParams();
  if (state.q.trim()) query.set("q", state.q.trim());
  if (state.type) query.set("type", state.type);
  if (state.entityType) query.set("entity_type", state.entityType);
  if (state.offset > 0) query.set("offset", String(state.offset));
  if (state.eventId) query.set("event", state.eventId);
  return query.toString();
}

export function hasActivityFilters(state: ActivityUrlState): boolean {
  return Boolean(state.q.trim() || state.type || state.entityType);
}
