import type { WebhookDeliveryStatus, WebhookEventType } from "@/types/api";

export const SUBSCRIBABLE_WEBHOOK_EVENTS = [
  "lead.created",
  "lead.qualified",
  "draft.approved",
  "email.sent",
] as const satisfies readonly WebhookEventType[];

export const webhookEventLabels: Record<WebhookEventType, string> = {
  "lead.created": "Lead created",
  "lead.qualified": "Lead analyzed by AI",
  "draft.approved": "Reply draft approved",
  "email.sent": "Email sent",
  "webhook.test": "Test event",
};

export const webhookEventHints: Record<WebhookEventType, string> = {
  "lead.created": "Lead ID, name, email, company, source, and status.",
  "lead.qualified": "Lead ID and the AI outcome, intent, and confidence.",
  "draft.approved": "Lead ID and draft ID. The reply text is not included.",
  "email.sent":
    "Lead ID, email ID, and draft ID. The message body is not included.",
  "webhook.test": "A sample message with no customer data.",
};

export const webhookDeliveryStatusLabels: Record<
  WebhookDeliveryStatus,
  string
> = {
  PENDING: "Waiting",
  SENDING: "Sending",
  DELIVERED: "Delivered",
  FAILED: "Failed",
};

export const webhookDeliveryStatusBadge = {
  PENDING: "pending",
  SENDING: "pending",
  DELIVERED: "success",
  FAILED: "failed",
} as const satisfies Record<WebhookDeliveryStatus, string>;
