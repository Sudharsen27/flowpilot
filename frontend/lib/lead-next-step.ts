import type { Lead } from "@/types/api";

export type LeadNextStepKind =
  | "resolve-attention"
  | "review-draft"
  | "send-response"
  | "retry-send"
  | "open-follow-up"
  | "schedule-follow-up"
  | "analyze"
  | "draft-response";

export type LeadNextStep = {
  kind: LeadNextStepKind;
  label: string;
  hint: string;
};

export function hasReviewableDraft(lead: Lead) {
  const draft = lead.latest_response_draft;
  if (!draft || draft.status !== "COMPLETED") return false;
  return draft.review_status !== "REJECTED";
}

function emailAlreadySent(lead: Lead) {
  return lead.latest_sales_run?.email_send?.status === "SENT";
}

/**
 * Shared salesperson next-step priority for leads list and detail.
 * Aligns with Customer 360 post-send cases (failed send, overdue FU, schedule).
 */
export function leadNextStep(lead: Lead): LeadNextStep {
  if (lead.human_attention_required) {
    return {
      kind: "resolve-attention",
      label: "Open lead",
      hint: "This lead needs a person to review it. Open the lead to resolve it.",
    };
  }

  const draft = lead.latest_response_draft;
  if (hasReviewableDraft(lead)) {
    if (draft?.review_status === "APPROVED" && !emailAlreadySent(lead)) {
      return {
        kind: "send-response",
        label: "Send response",
        hint: "The reply is approved but not sent. Open Approvals to send it — approval alone does not email the customer.",
      };
    }
    if (draft?.review_status === "GENERATED" || draft?.review_status === "EDITED") {
      return {
        kind: "review-draft",
        label: "Review draft",
        hint: "An AI reply is waiting. Review, edit, approve, or reject it.",
      };
    }
  }

  const summary = lead.latest_sales_run;
  if (summary?.email_send?.status === "FAILED") {
    return {
      kind: "retry-send",
      label: "Retry send",
      hint: "The latest outbound email could not be delivered. Open the lead to review and retry from Approvals or Sales Agent history.",
    };
  }

  const followUp = summary?.follow_up ?? null;
  if (followUp?.status === "PENDING" && followUp.is_overdue) {
    return {
      kind: "open-follow-up",
      label: "Open follow-ups",
      hint: "A scheduled follow-up is overdue. Open Follow-ups to review or complete it.",
    };
  }

  if (
    summary?.email_send?.status === "SENT" &&
    (!followUp || followUp.status !== "PENDING")
  ) {
    return {
      kind: "schedule-follow-up",
      label: "Schedule follow-up",
      hint: "The response was sent. Schedule a follow-up so the next touch is not missed.",
    };
  }

  if (followUp?.status === "PENDING") {
    return {
      kind: "open-follow-up",
      label: "Open follow-ups",
      hint: "A follow-up is scheduled for this customer. Open Follow-ups to review timing.",
    };
  }

  const qualification = lead.latest_qualification;
  if (!qualification || qualification.status === "FAILED") {
    return {
      kind: "analyze",
      label: "Analyze with AI",
      hint: "Ask AI to assess the enquiry. The lead's status does not change.",
    };
  }
  return {
    kind: "draft-response",
    label: "Draft response",
    hint: "Ask AI to write a reply. Nothing is sent until you approve and send it.",
  };
}
