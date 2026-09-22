import { describe, expect, it } from "vitest";

import {
  deriveCustomer360NextStep,
  leadNeedsApproval,
} from "@/lib/customer-360-state";
import type { InboxConversationResponse, Lead } from "@/types/api";

const baseLead: Lead = {
  id: "lead-1",
  name: "Ada Prospect",
  email: "ada@example.com",
  phone: null,
  company: "Acme",
  source: "WEBSITE",
  status: "NEW",
  notes: null,
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-10T10:00:00Z",
};

function conversation(
  overrides: Partial<InboxConversationResponse["lead"]> = {},
): InboxConversationResponse {
  return {
    lead: {
      lead_id: "lead-1",
      name: "Ada Prospect",
      email: "ada@example.com",
      phone: null,
      company: "Acme",
      source: "WEBSITE",
      lead_status: "NEW",
      enquiry: null,
      conversation_state: "OPEN",
      needs_approval: false,
      latest_draft: null,
      latest_sales_run: null,
      ...overrides,
    },
    items: [],
    total_items: 0,
  };
}

describe("customer-360-state", () => {
  it("detects needs-approval from conversation, sales run, or draft review", () => {
    expect(leadNeedsApproval(baseLead)).toBe(false);
    expect(
      leadNeedsApproval(baseLead, conversation({ needs_approval: true })),
    ).toBe(true);
    expect(
      leadNeedsApproval({
        ...baseLead,
        latest_sales_run: {
          id: "run-1",
          agent_id: "agent-1",
          status: "WAITING_APPROVAL",
          stage: "AWAIT_APPROVAL",
          email_send: null,
          follow_up: null,
        },
      }),
    ).toBe(true);
    expect(
      leadNeedsApproval({
        ...baseLead,
        latest_response_draft: {
          id: "draft-1",
          status: "COMPLETED",
          review_status: "EDITED",
          created_at: "2026-09-11T10:00:00Z",
        },
      }),
    ).toBe(true);
  });

  it("derives review, follow-up, completed, and idle next steps from real state", () => {
    expect(deriveCustomer360NextStep(baseLead).title).toBe("No action required");

    expect(
      deriveCustomer360NextStep({
        ...baseLead,
        latest_response_draft: {
          id: "draft-1",
          status: "COMPLETED",
          review_status: "GENERATED",
          created_at: "2026-09-11T10:00:00Z",
        },
      }).title,
    ).toBe("Review AI response");

    expect(
      deriveCustomer360NextStep({
        ...baseLead,
        latest_sales_run: {
          id: "run-1",
          agent_id: "agent-1",
          status: "COMPLETED",
          stage: "DONE",
          email_send: { status: "SENT", completed_at: "2026-09-11T11:00:00Z" },
          follow_up: {
            status: "PENDING",
            due_at: "2026-09-12T10:00:00Z",
            is_overdue: true,
          },
        },
      }).title,
    ).toBe("Follow-up overdue");

    expect(
      deriveCustomer360NextStep({
        ...baseLead,
        latest_sales_run: {
          id: "run-1",
          agent_id: "agent-1",
          status: "COMPLETED",
          stage: "DONE",
          email_send: { status: "SENT", completed_at: "2026-09-11T11:00:00Z" },
          follow_up: null,
        },
      }).title,
    ).toBe("Sales Agent completed");

    expect(
      deriveCustomer360NextStep({
        ...baseLead,
        latest_sales_run: {
          id: "run-1",
          agent_id: "agent-1",
          status: "FAILED",
          stage: "SEND",
          email_send: { status: "FAILED", completed_at: null },
          follow_up: null,
        },
      }).title,
    ).toBe("Email send failed");
  });
});
