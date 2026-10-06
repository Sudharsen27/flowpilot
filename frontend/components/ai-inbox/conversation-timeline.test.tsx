import { render, screen } from "@testing-library/react";
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
});