/** Mirrors the backend 36-character bound on lead, agent and Sales Run IDs. */
const MAX_ID_LENGTH = 36;

export type LeadSalesRunSelection = {
  salesRunId: string;
  agentId: string;
};

function parseId(raw: string | null | undefined): string | null {
  const value = raw?.trim() ?? "";
  if (!value || value.length > MAX_ID_LENGTH) return null;
  return value;
}

/**
 * Sales Run selection on the lead page. Both IDs are required because the
 * existing Sales Run detail endpoint is scoped by agent.
 */
export function parseLeadSalesRunSearchParams(
  searchParams: URLSearchParams,
): LeadSalesRunSelection | null {
  const salesRunId = parseId(searchParams.get("sales_run"));
  const agentId = parseId(searchParams.get("agent"));
  return salesRunId && agentId ? { salesRunId, agentId } : null;
}

/**
 * Build a lead detail href. A complete `salesRun` selection opens that run in
 * the lead's Sales Agent history; anything incomplete links to the lead only.
 */
export function buildLeadHref(
  leadId: string,
  options: { salesRunId?: string | null; agentId?: string | null } = {},
): string | null {
  const lead = parseId(leadId);
  if (!lead) return null;
  const path = `/leads/${encodeURIComponent(lead)}`;
  const salesRunId = parseId(options.salesRunId);
  const agentId = parseId(options.agentId);
  if (!salesRunId || !agentId) return path;
  const query = new URLSearchParams({ sales_run: salesRunId, agent: agentId });
  return `${path}?${query.toString()}`;
}
