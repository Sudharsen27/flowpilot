import { buildAgentExecutionsHref } from "@/lib/agent-executions-url";
import { buildApprovalsHref } from "@/lib/approvals-url";
import { buildLeadHref } from "@/lib/lead-url";
import type { ActivityEvent, ApprovalQueueStatus } from "@/types/api";

export type ActivityDestination = {
  href: string;
  /** Visible action text, e.g. "Open lead". */
  label: string;
};

/** Entity types that never navigate from activity in this phase. */
const UNLINKED_ENTITY_TYPES = new Set<ActivityEvent["entity_type"]>([
  "KNOWLEDGE_ENTRY",
  "WORKFLOW_RULE",
  "WEBHOOK_ENDPOINT",
  "COMPANY_PROSPECT",
]);

/**
 * Queue that held the draft when the event was recorded. Only a fallback for
 * responses without `draft_approval_status`; the draft may have moved since.
 */
function approvalStatusFor(eventStatus: string | null): ApprovalQueueStatus {
  if (eventStatus === "APPROVED") return "approved";
  if (eventStatus === "REJECTED") return "rejected";
  return "pending";
}

function leadDestination(event: ActivityEvent): ActivityDestination | null {
  if (!event.lead_id) return null;
  const href = buildLeadHref(event.lead_id);
  return href ? { href, label: "Open lead" } : null;
}

/**
 * Resolve where an activity event links to, using existing routes only.
 * Destinations refetch through organization-scoped endpoints, so a record that
 * is missing or belongs to another organization shows that page's own
 * not-found state. Returns null when the event has nothing to open.
 */
export function activityDestination(
  event: ActivityEvent,
): ActivityDestination | null {
  if (UNLINKED_ENTITY_TYPES.has(event.entity_type)) return null;

  switch (event.entity_type) {
    case "AGENT_EXECUTION": {
      const executionId = event.execution_id ?? event.entity_id;
      if (event.agent_id && executionId) {
        const href = buildAgentExecutionsHref({
          agentId: event.agent_id,
          executionId,
        });
        if (href.includes("execution=")) {
          return { href, label: "Open execution" };
        }
      }
      break;
    }
    case "LEAD_RESPONSE_DRAFT": {
      const draftId = event.draft_id ?? event.entity_id;
      // Prefer the draft's current queue; null means no queue lists it any more.
      const queue =
        event.draft_approval_status === undefined
          ? approvalStatusFor(event.status)
          : event.draft_approval_status;
      if (draftId && queue) {
        return {
          href: buildApprovalsHref({ approvalId: draftId, status: queue }),
          label: "Open approval",
        };
      }
      break;
    }
    case "SALES_RUN": {
      const salesRunId = event.sales_run_id ?? event.entity_id;
      if (event.lead_id && event.agent_id && salesRunId) {
        const href = buildLeadHref(event.lead_id, {
          salesRunId,
          agentId: event.agent_id,
        });
        if (href?.includes("sales_run=")) {
          return { href, label: "Open sales run" };
        }
      }
      break;
    }
    default:
      break;
  }

  return leadDestination(event);
}
