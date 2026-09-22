import type {
  InboxConversationResponse,
  Lead,
  LeadLatestSalesRunSummary,
  LeadResponseReviewStatus,
} from "@/types/api";

export type Customer360NextStepKind =
  | "review"
  | "follow-up"
  | "progress"
  | "failed"
  | "complete"
  | "idle";

export type Customer360NextStep = {
  kind: Customer360NextStepKind;
  title: string;
  description: string;
};

export function leadNeedsApproval(
  lead: Lead,
  conversation?: InboxConversationResponse | null,
): boolean {
  if (conversation?.lead.needs_approval) return true;
  if (lead.latest_sales_run?.status === "WAITING_APPROVAL") return true;
  const review = lead.latest_response_draft?.review_status;
  return review === "GENERATED" || review === "EDITED";
}

function draftNeedsReview(status: LeadResponseReviewStatus | null | undefined) {
  return status === "GENERATED" || status === "EDITED";
}

function followUpLabel(followUp: LeadLatestSalesRunSummary["follow_up"]) {
  if (!followUp) return null;
  if (followUp.status === "PENDING" && followUp.is_overdue) {
    return {
      kind: "follow-up" as const,
      title: "Follow-up overdue",
      description:
        "A scheduled follow-up is overdue. Open Follow-ups to review or complete it.",
    };
  }
  if (followUp.status === "PENDING") {
    return {
      kind: "follow-up" as const,
      title: "Follow-up scheduled",
      description:
        "A follow-up is scheduled for this customer. Open Follow-ups to review timing.",
    };
  }
  return null;
}

/**
 * Derive the salesperson's current next step from real Lead / Sales Run /
 * Inbox conversation state only. Does not invent recommendations.
 */
export function deriveCustomer360NextStep(
  lead: Lead,
  conversation?: InboxConversationResponse | null,
): Customer360NextStep {
  const summary = lead.latest_sales_run;
  const draftReview = lead.latest_response_draft?.review_status;
  const needsApproval = leadNeedsApproval(lead, conversation);

  if (needsApproval || draftNeedsReview(draftReview)) {
    return {
      kind: "review",
      title: "Review AI response",
      description:
        "An AI-generated draft is waiting for human review. Approval does not send the email by itself.",
    };
  }

  if (summary?.email_send?.status === "FAILED") {
    return {
      kind: "failed",
      title: "Email send failed",
      description:
        "The latest outbound email could not be delivered. Review Sales Agent history for details.",
    };
  }

  const followUp = followUpLabel(summary?.follow_up ?? null);
  if (followUp) return followUp;

  if (summary?.status === "RUNNING") {
    return {
      kind: "progress",
      title: "Sales Agent in progress",
      description: `The Sales Agent is at the ${stagePhrase(summary.stage)} stage.`,
    };
  }

  if (summary?.status === "FAILED") {
    return {
      kind: "failed",
      title: "Sales Agent failed",
      description:
        "The latest Sales Agent run failed. Open Sales Agent history to inspect the record.",
    };
  }

  if (summary?.status === "CANCELLED") {
    return {
      kind: "idle",
      title: "Sales Agent cancelled",
      description:
        "The latest Sales Agent run was cancelled. Start a new run when you are ready.",
    };
  }

  if (summary?.status === "COMPLETED") {
    if (summary.follow_up?.status === "COMPLETED") {
      return {
        kind: "complete",
        title: "Sales Agent completed",
        description:
          "The Sales Agent run and its follow-up are complete. No action is required right now.",
      };
    }
    return {
      kind: "complete",
      title: "Sales Agent completed",
      description:
        "The latest Sales Agent run finished. No approval action is waiting.",
    };
  }

  if (draftReview === "REJECTED") {
    return {
      kind: "idle",
      title: "Draft rejected",
      description:
        "The latest AI draft was rejected. Start a new Sales Agent run or draft when ready.",
    };
  }

  if (draftReview === "APPROVED" && summary?.email_send?.status !== "SENT") {
    return {
      kind: "idle",
      title: "Draft approved",
      description:
        "The AI draft was approved. Sending still uses the existing Sales Agent send step.",
    };
  }

  if (!summary && !lead.latest_qualification && !lead.latest_response_draft) {
    return {
      kind: "idle",
      title: "No action required",
      description:
        "No Sales Agent activity yet. Start a run to qualify the enquiry and prepare a draft.",
    };
  }

  return {
    kind: "idle",
    title: "No action required",
    description: "Nothing is waiting for your review on this customer right now.",
  };
}

function stagePhrase(stage: LeadLatestSalesRunSummary["stage"]) {
  const labels: Record<LeadLatestSalesRunSummary["stage"], string> = {
    MATCH_LEAD: "match lead",
    QUALIFY: "qualify",
    DRAFT: "draft",
    AWAIT_APPROVAL: "await approval",
    SEND: "send",
    DONE: "done",
  };
  return labels[stage];
}
