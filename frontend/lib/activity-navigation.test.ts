import { describe, expect, it } from "vitest";

import { activityDestination } from "@/lib/activity-navigation";
import type { ActivityEvent } from "@/types/api";

function event(overrides: Partial<ActivityEvent> = {}): ActivityEvent {
  return {
    id: "act-1",
    type: "SYSTEM_EVENT",
    title: "Event",
    summary: null,
    occurred_at: "2026-10-28T10:00:00Z",
    actor_type: "SYSTEM",
    actor_user_id: null,
    agent_id: null,
    entity_type: "LEAD",
    entity_id: "lead-1",
    lead_id: "lead-1",
    status: null,
    sales_run_id: null,
    execution_id: null,
    email_send_id: null,
    follow_up_id: null,
    follow_up_execution_id: null,
    draft_id: null,
    qualification_id: null,
    ...overrides,
  };
}

describe("activityDestination", () => {
  it("opens lead details for lead events", () => {
    expect(activityDestination(event())).toEqual({
      href: "/leads/lead-1",
      label: "Open lead",
    });
  });

  it("opens the execution detail panel with the event's agent", () => {
    expect(
      activityDestination(
        event({
          type: "AI_ACTION",
          entity_type: "AGENT_EXECUTION",
          entity_id: "exec-1",
          execution_id: "exec-1",
          agent_id: "agent-1",
        }),
      ),
    ).toEqual({
      href: "/agents/executions?agent_id=agent-1&execution=exec-1",
      label: "Open execution",
    });
  });

  it("falls back to the lead when an execution event has no agent", () => {
    expect(
      activityDestination(
        event({
          entity_type: "AGENT_EXECUTION",
          entity_id: "exec-1",
          execution_id: "exec-1",
          agent_id: null,
        }),
      ),
    ).toEqual({ href: "/leads/lead-1", label: "Open lead" });
    expect(
      activityDestination(
        event({
          entity_type: "AGENT_EXECUTION",
          entity_id: "exec-1",
          execution_id: "exec-1",
          agent_id: null,
          lead_id: null,
        }),
      ),
    ).toBeNull();
  });

  it.each([
    ["GENERATED", "/approvals?approval=draft-1"],
    ["EDITED", "/approvals?approval=draft-1"],
    [null, "/approvals?approval=draft-1"],
    ["APPROVED", "/approvals?status=approved&approval=draft-1"],
    ["REJECTED", "/approvals?status=rejected&approval=draft-1"],
  ])("opens the approval for a %s draft event", (status, href) => {
    expect(
      activityDestination(
        event({
          type: "APPROVAL",
          entity_type: "LEAD_RESPONSE_DRAFT",
          entity_id: "draft-1",
          draft_id: "draft-1",
          status,
        }),
      ),
    ).toEqual({ href, label: "Open approval" });
  });

  describe("draft events with the draft's current approval queue", () => {
    function draftEvent(overrides: Partial<ActivityEvent>) {
      return event({
        type: "AI_ACTION",
        entity_type: "LEAD_RESPONSE_DRAFT",
        entity_id: "draft-1",
        draft_id: "draft-1",
        status: "GENERATED",
        ...overrides,
      });
    }

    it.each([
      ["pending", "/approvals?approval=draft-1"],
      ["approved", "/approvals?status=approved&approval=draft-1"],
      ["rejected", "/approvals?status=rejected&approval=draft-1"],
    ] as const)("opens the %s queue the draft is in now", (queue, href) => {
      expect(activityDestination(draftEvent({ draft_approval_status: queue }))).toEqual({
        href,
        label: "Open approval",
      });
    });

    it("follows the current queue, not the status recorded on the event", () => {
      expect(
        activityDestination(
          draftEvent({ status: "GENERATED", draft_approval_status: "approved" }),
        )?.href,
      ).toBe("/approvals?status=approved&approval=draft-1");
      expect(
        activityDestination(
          draftEvent({ status: "APPROVED", draft_approval_status: "rejected" }),
        )?.href,
      ).toBe("/approvals?status=rejected&approval=draft-1");
    });

    it("falls back to the lead when no queue lists the draft (missing, failed or other organization)", () => {
      expect(activityDestination(draftEvent({ draft_approval_status: null }))).toEqual({
        href: "/leads/lead-1",
        label: "Open lead",
      });
      expect(
        activityDestination(draftEvent({ draft_approval_status: null, lead_id: null })),
      ).toBeNull();
    });

    it("keeps the recorded-status mapping when the API omits the current queue", () => {
      expect(activityDestination(draftEvent({ status: "REJECTED" }))?.href).toBe(
        "/approvals?status=rejected&approval=draft-1",
      );
    });
  });

  it("opens the Sales Run in the lead's Sales Agent history", () => {
    expect(
      activityDestination(
        event({
          type: "AI_ACTION",
          entity_type: "SALES_RUN",
          entity_id: "run-1",
          sales_run_id: "run-1",
          agent_id: "agent-1",
        }),
      ),
    ).toEqual({
      href: "/leads/lead-1?sales_run=run-1&agent=agent-1",
      label: "Open sales run",
    });
  });

  it("falls back to the lead when a Sales Run event has no agent, and to nothing without a lead", () => {
    expect(
      activityDestination(
        event({ entity_type: "SALES_RUN", entity_id: "run-1", sales_run_id: "run-1" }),
      ),
    ).toEqual({ href: "/leads/lead-1", label: "Open lead" });
    expect(
      activityDestination(
        event({
          entity_type: "SALES_RUN",
          entity_id: "run-1",
          sales_run_id: "run-1",
          agent_id: "agent-1",
          lead_id: null,
        }),
      ),
    ).toBeNull();
  });

  it.each([
    "LEAD_EMAIL_SEND",
    "LEAD_FOLLOW_UP",
    "LEAD_FOLLOW_UP_EXECUTION",
    "LEAD_QUALIFICATION",
  ] as const)("falls back to lead details for %s events", (entityType) => {
    expect(
      activityDestination(event({ entity_type: entityType, entity_id: "other-1" })),
    ).toEqual({ href: "/leads/lead-1", label: "Open lead" });
  });

  it.each([
    "KNOWLEDGE_ENTRY",
    "WORKFLOW_RULE",
    "WEBHOOK_ENDPOINT",
    "COMPANY_PROSPECT",
  ] as const)("does not link %s events", (entityType) => {
    expect(
      activityDestination(event({ entity_type: entityType, entity_id: "other-1" })),
    ).toBeNull();
  });

  it("does not link events without any usable identifier", () => {
    expect(
      activityDestination(event({ entity_type: "LEAD_EMAIL_SEND", lead_id: null })),
    ).toBeNull();
    expect(activityDestination(event({ lead_id: "x".repeat(37) }))).toBeNull();
  });

  it("encodes identifiers and drops oversized ones", () => {
    expect(activityDestination(event({ lead_id: "lead/1" }))?.href).toBe(
      "/leads/lead%2F1",
    );
    expect(
      activityDestination(
        event({
          entity_type: "AGENT_EXECUTION",
          entity_id: "e".repeat(37),
          execution_id: "e".repeat(37),
          agent_id: "agent-1",
        }),
      ),
    ).toEqual({ href: "/leads/lead-1", label: "Open lead" });
  });
});
