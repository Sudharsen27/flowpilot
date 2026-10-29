import { isDealStage, isForecastCategory } from "@/lib/deals";
import type { DealStage, ForecastCategory } from "@/types/api";

export type DealsUrlState = {
  q: string;
  stage: DealStage | null;
  /** Open deals in this category (closed deals have none). */
  forecastCategory: ForecastCategory | null;
  ownerUserId: string | null;
  closeDateFrom: string | null;
  closeDateTo: string | null;
  offset: number;
  /** Open the create form, optionally linked to a lead (`?create=1&lead_id=…`). */
  create: boolean;
  leadId: string | null;
};

export const DEALS_PATH = "/deals";
export const DEALS_PAGE_SIZE = 20;
const MAX_ID_LENGTH = 36;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function parseId(raw: string | null): string | null {
  const value = raw?.trim() ?? "";
  return value && value.length <= MAX_ID_LENGTH ? value : null;
}

function parseDate(raw: string | null): string | null {
  const value = raw?.trim() ?? "";
  if (!DATE_PATTERN.test(value)) return null;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().startsWith(value) ? value : null;
}

export function parseDealsSearchParams(searchParams: URLSearchParams): DealsUrlState {
  const stage = searchParams.get("stage")?.trim().toUpperCase() ?? "";
  const category = searchParams.get("category")?.trim().toUpperCase() ?? "";
  const offsetRaw = searchParams.get("offset")?.trim() ?? "";
  const offset = /^\d+$/.test(offsetRaw) ? Number.parseInt(offsetRaw, 10) : 0;
  return {
    q: (searchParams.get("q") ?? "").trim().slice(0, 200),
    stage: isDealStage(stage) ? stage : null,
    forecastCategory: isForecastCategory(category) ? category : null,
    ownerUserId: parseId(searchParams.get("owner")),
    closeDateFrom: parseDate(searchParams.get("from")),
    closeDateTo: parseDate(searchParams.get("to")),
    offset: Number.isSafeInteger(offset) ? offset : 0,
    create: searchParams.get("create") === "1",
    leadId: parseId(searchParams.get("lead_id")),
  };
}

export function serializeDealsSearchParams(state: DealsUrlState): string {
  const query = new URLSearchParams();
  if (state.q.trim()) query.set("q", state.q.trim());
  if (state.stage) query.set("stage", state.stage);
  if (state.forecastCategory) query.set("category", state.forecastCategory);
  if (state.ownerUserId) query.set("owner", state.ownerUserId);
  if (state.closeDateFrom) query.set("from", state.closeDateFrom);
  if (state.closeDateTo) query.set("to", state.closeDateTo);
  if (state.offset > 0) query.set("offset", String(state.offset));
  if (state.create) query.set("create", "1");
  if (state.create && state.leadId) query.set("lead_id", state.leadId);
  return query.toString();
}

export function hasDealFilters(state: DealsUrlState): boolean {
  return Boolean(
    state.q ||
      state.stage ||
      state.forecastCategory ||
      state.ownerUserId ||
      state.closeDateFrom ||
      state.closeDateTo,
  );
}

/** Link that opens the create form prefilled with a lead. */
export function buildCreateDealHref(leadId: string): string {
  const query = serializeDealsSearchParams({
    q: "",
    stage: null,
    forecastCategory: null,
    ownerUserId: null,
    closeDateFrom: null,
    closeDateTo: null,
    offset: 0,
    create: true,
    leadId,
  });
  return `${DEALS_PATH}?${query}`;
}

export function buildDealHref(dealId: string): string {
  return `${DEALS_PATH}/${encodeURIComponent(dealId)}`;
}
