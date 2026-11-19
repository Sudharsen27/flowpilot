import { describe, expect, it } from "vitest";

import { leadNextStep } from "@/lib/lead-next-step";
import type { Lead } from "@/types/api";

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

describe("leadNextStep", () => {
  it("suggests review for generated drafts and send for approved drafts", () => {
    expect(
      leadNextStep({
        ...baseLead,
        latest_response_draft: {
          id: "draft-1",
          status: "COMPLETED",
          review_status: "GENERATED",
          created_at: "2026-09-11T10:00:00Z",
        },
      }),
    ).toMatchObject({ kind: "review-draft", label: "Review draft" });

    expect(
      leadNextStep({
        ...baseLead,
        latest_response_draft: {
          id: "draft-1",
          status: "COMPLETED",
          review_status: "APPROVED",
          created_at: "2026-09-11T10:00:00Z",
        },
      }),
    ).toMatchObject({ kind: "send-response", label: "Send response" });
  });

  it("covers failed send, overdue follow-up, and post-send schedule", () => {
    expect(
      leadNextStep({
        ...baseLead,
        latest_sales_run: {
          id: "run-1",
          agent_id: "agent-1",
          status: "COMPLETED",
          stage: "DONE",
          email_send: { status: "FAILED", completed_at: null },
          follow_up: null,
        },
      }),
    ).toMatchObject({ kind: "retry-send", label: "Retry send" });

    expect(
      leadNextStep({
        ...baseLead,
        latest_sales_run: {
          id: "run-1",
          agent_id: "agent-1",
          status: "COMPLETED",
          stage: "DONE",
          email_send: { status: "SENT", completed_at: "2026-09-11T11:00:00Z" },
          follow_up: {
            status: "PENDING",
            due_at: "2026-09-10T10:00:00Z",
            is_overdue: true,
          },
        },
      }),
    ).toMatchObject({ kind: "open-follow-up", label: "Open follow-ups" });

    expect(
      leadNextStep({
        ...baseLead,
        latest_response_draft: {
          id: "draft-1",
          status: "COMPLETED",
          review_status: "APPROVED",
          created_at: "2026-09-11T10:00:00Z",
        },
        latest_sales_run: {
          id: "run-1",
          agent_id: "agent-1",
          status: "COMPLETED",
          stage: "DONE",
          email_send: { status: "SENT", completed_at: "2026-09-11T11:00:00Z" },
          follow_up: null,
        },
      }),
    ).toMatchObject({ kind: "schedule-follow-up", label: "Schedule follow-up" });
  });
});
