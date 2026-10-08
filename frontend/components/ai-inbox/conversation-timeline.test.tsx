import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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

  it("qualifies an unmatched reply and shows an existing qualification without sending", async () => {
    const user = userEvent.setup();
    const onQualifyReply = vi.fn();
    const { rerender } = render(
      <ConversationTimeline
        items={[
          item({
            id: "evt-reply",
            kind: "CUSTOMER_REPLY",
            direction: "inbound",
            title: "Customer reply received",
            body: "I can talk Thursday.",
            actor_type: "PUBLIC_VISITOR",
            inbound_email_id: "email-1",
          }),
        ]}
        onQualifyReply={onQualifyReply}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Qualify this reply" }));
    expect(onQualifyReply).toHaveBeenCalledWith("email-1");
    expect(screen.getByText("Reads this reply only. It does not draft or send an email.")).toBeVisible();

    rerender(
      <ConversationTimeline
        items={[
          item({
            id: "evt-reply",
            kind: "CUSTOMER_REPLY",
            direction: "inbound",
            title: "Customer reply received",
            body: "I can talk Thursday.",
            actor_type: "PUBLIC_VISITOR",
            inbound_email_id: "email-1",
          }),
          item({
            id: "evt-qualified",
            kind: "QUALIFICATION_COMPLETED",
            title: "Lead qualified",
            actor_type: "AGENT",
            inbound_email_id: "email-1",
            qualification_intent: "REQUEST_DEMO",
            qualification_outcome: "NEEDS_MORE_INFORMATION",
            buying_signals: ["Asked to schedule a demo"],
            occurred_at: "2026-09-17T10:00:00Z",
          }),
        ]}
      />,
    );

    expect(screen.queryByRole("button", { name: "Qualify this reply" })).not.toBeInTheDocument();
    expect(screen.getByText("This reply has been qualified. No email was sent.")).toBeVisible();
    expect(screen.getByText("Needs more information · Demo request")).toBeVisible();
    expect(screen.getByText("Asked to schedule a demo")).toBeVisible();
  });
});