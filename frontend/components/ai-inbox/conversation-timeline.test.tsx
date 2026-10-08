import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConversationTimeline } from "@/components/ai-inbox/conversation-timeline";
import type { InboxTimelineItem } from "@/types/api";

function item(
  overrides: Partial<InboxTimelineItem> & Pick<InboxTimelineItem, "id" | "kind" | "title">,
): InboxTimelineItem {
  return {
    direction: "internal",
    occurred_at: "2026-09-22T11:00:00Z",
    summary: null,
    body: null,
    status: null,
    actor_type: "AGENT",
    actor_user_id: null,
    agent_id: null,
    source_entity_type: "LEAD",
    source_entity_id: "lead-1",
    activity_id: overrides.id,
    is_draft: false,
    is_sent_message: false,
    ...overrides,
  };
}

describe("Conversation timeline human attention", () => {
  it("renders human attention required and resolved events", () => {
    render(
      <ConversationTimeline
        items={[
          item({
            id: "evt-required",
            kind: "HUMAN_ATTENTION_REQUIRED",
            title: "Human attention required",
            summary: "The AI decision flagged this lead for human attention.",
          }),
          item({
            id: "evt-resolved",
            kind: "HUMAN_ATTENTION_RESOLVED",
            title: "Human attention resolved",
            summary: "A team member resolved human attention for this lead.",
            actor_type: "USER",
          }),
        ]}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Human attention required" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Human attention resolved" }),
    ).toBeVisible();
    expect(screen.queryByText("Needs your review")).not.toBeInTheDocument();
    expect(screen.getAllByText("Human attention").length).toBeGreaterThan(0);
  });

  it("renders an inbound customer reply apart from a sent email", () => {
    render(
      <ConversationTimeline
        items={[
          item({
            id: "evt-reply",
            kind: "CUSTOMER_REPLY",
            direction: "inbound",
            title: "Customer reply received",
            summary: "An inbound customer email was linked to this lead.",
            body: "I can talk Thursday.",
            actor_type: "PUBLIC_VISITOR",
            occurred_at: "2026-09-17T09:30:00Z",
          }),
          item({
            id: "evt-sent",
            kind: "EMAIL_SENT",
            direction: "outbound",
            title: "Email sent",
            body: "Sent email body",
            actor_type: "USER",
            is_sent_message: true,
            occurred_at: "2026-09-17T10:10:00Z",
            source_entity_type: "LEAD_EMAIL_SEND",
          }),
        ]}
      />,
    );

    const timeline = screen.getByRole("list", { name: "Conversation timeline" });
    expect(within(timeline).getByRole("heading", { name: "Customer reply" })).toBeVisible();
    expect(within(timeline).getByText("I can talk Thursday.")).toBeVisible();
    expect(within(timeline).queryByText("Website visitor")).not.toBeInTheDocument();
    expect(within(timeline).getByText("Sent")).toBeVisible();
    expect(within(timeline).getByText("Sent email body")).toBeVisible();
    const headings = within(timeline).getAllByRole("heading");
    expect(headings.map((heading) => heading.textContent)).toEqual([
      "Customer reply",
      "Email sent",
    ]);
  });
});