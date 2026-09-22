import type { InboxConversationState, LeadSource } from "@/types/api";

export const inboxSourceLabels: Record<LeadSource, string> = {
  MANUAL: "Manual",
  WEBSITE: "Website",
  EMAIL: "Email",
  CHAT: "Chat",
  API: "API",
  IMPORT: "Import",
};

export const inboxStateLabels: Record<InboxConversationState, string> = {
  OPEN: "Open",
  NEEDS_APPROVAL: "Needs approval",
  CLOSED: "Closed",
};

export const draftReviewLabels = {
  GENERATED: "Generated",
  EDITED: "Edited",
  APPROVED: "Approved",
  REJECTED: "Rejected",
} as const;
