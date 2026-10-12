import type { Lead } from "@/types/api";

export type LeadNextStepKind =
  | "resolve-attention"
  | "review-draft"
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

export function leadNextStep(lead: Lead): LeadNextStep {
  if (lead.human_attention_required) {
    return {
      kind: "resolve-attention",
      label: "Open lead",
      hint: "This lead needs a person to review it. Open the lead to resolve it.",
    };
  }
  if (hasReviewableDraft(lead)) {
    return {
      kind: "review-draft",
      label: "Review draft",
      hint:
        lead.latest_response_draft?.review_status === "APPROVED"
          ? "A reply is approved but not sent. Review it and send it yourself."
          : "An AI reply is waiting. Review, edit, approve, or reject it.",
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
