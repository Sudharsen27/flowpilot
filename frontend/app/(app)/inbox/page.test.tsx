import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InboxPage from "@/app/(app)/inbox/page";
import { getInbox, getInboxConversation } from "@/lib/api/inbox";
import type {
  InboxConversationResponse,
  InboxItem,
  InboxListResponse,
  InboxTimelineItem,
} from "@/types/api";

vi.mock("@/lib/api/inbox", () => ({
  getInbox: vi.fn(),
  getInboxConversation: vi.fn(),
}));

const getInboxMock = vi.mocked(getInbox);
const getInboxConversationMock = vi.mocked(getInboxConversation);

const inboxItem: InboxItem = {
  lead_id: "lead-1",
  name: "Ada Lovelace",
  email: "ada@example.com",
  company: "Analytical Engines",
  source: "WEBSITE",
  lead_status: "NEW",
  conversation_state: "NEEDS_APPROVAL",
  needs_approval: true,
  last_activity_at: "2026-09-17T10:00:00Z",
  last_activity_type: "AI_ACTION",
  last_activity_title: "Response draft generated",
  preview: "Thanks for writing — happy to share a demo slot.",
  latest_draft: {
    id: "draft-1",
    status: "COMPLETED",
    review_status: "GENERATED",
    created_at: "2026-09-17T09:55:00Z",
  },
  latest_email_status: null,
  latest_sales_run: null,
  latest_follow_up_status: null,
  latest_follow_up_overdue: null,
};

const timelineItems: InboxTimelineItem[] = [
  {
    id: "evt-1",
    kind: "WEBSITE_ENQUIRY",
    direction: "inbound",
    occurred_at: "2026-09-17T09:00:00Z",
    title: "Website enquiry received",
    summary: "A visitor submitted a website enquiry.",
    body: "Please call me about pricing.",
    status: null,
    actor_type: "PUBLIC_VISITOR",
    actor_user_id: null,
    agent_id: null,
    source_entity_type: "LEAD",
    source_entity_id: "lead-1",
    activity_id: "evt-1",
    is_draft: false,
    is_sent_message: false,
  },
  {
    id: "evt-2",
    kind: "DRAFT_GENERATED",
    direction: "internal",
    occurred_at: "2026-09-17T09:55:00Z",
    title: "Response draft generated",
    summary: "AI drafted a customer response.",
    body: "Draft body text",
    status: "GENERATED",
    actor_type: "AGENT",
    actor_user_id: null,
    agent_id: "agent-1",
    source_entity_type: "LEAD_RESPONSE_DRAFT",
    source_entity_id: "draft-1",
    activity_id: "evt-2",
    is_draft: true,
    is_sent_message: false,
    draft_id: "draft-1",
  },
  {
    id: "evt-3",
    kind: "EMAIL_SENT",
    direction: "outbound",
    occurred_at: "2026-09-17T10:10:00Z",
    title: "Email sent",
    summary: "An email was sent to the lead.",
    body: "Sent email body",
    status: "SENT",
    actor_type: "USER",
    actor_user_id: "user-1",
    agent_id: null,
    source_entity_type: "LEAD_EMAIL_SEND",
    source_entity_id: "send-1",
    activity_id: "evt-3",
    is_draft: false,
    is_sent_message: true,
    email_send_id: "send-1",
  },
  {
    id: "evt-4",
    kind: "EMAIL_FAILED",
    direction: "outbound",
    occurred_at: "2026-09-17T10:20:00Z",
    title: "Email send failed",
    summary: "An email send failed.",
    body: "Failed email body",
    status: "FAILED",
    actor_type: "SYSTEM",
    actor_user_id: null,
    agent_id: null,
    source_entity_type: "LEAD_EMAIL_SEND",
    source_entity_id: "send-2",
    activity_id: "evt-4",
    is_draft: false,
    is_sent_message: false,
    email_send_id: "send-2",
  },
  {
    id: "evt-5",
    kind: "FOLLOW_UP_EXECUTION_SENT",
    direction: "outbound",
    occurred_at: "2026-09-17T11:00:00Z",
    title: "Follow-up executed",
    summary: "A follow-up email was sent.",
    body: "Follow-up body",
    status: "SENT",
    actor_type: "SYSTEM",
    actor_user_id: null,
    agent_id: null,
    source_entity_type: "LEAD_FOLLOW_UP_EXECUTION",
    source_entity_id: "exec-1",
    activity_id: "evt-5",
    is_draft: false,
    is_sent_message: true,
    follow_up_execution_id: "exec-1",
  },
];

const conversation: InboxConversationResponse = {
  lead: {
    lead_id: "lead-1",
    name: "Ada Lovelace",
    email: "ada@example.com",
    phone: "+1 555 0100",
    company: "Analytical Engines",
    source: "WEBSITE",
    lead_status: "NEW",
    enquiry: "Please call me about pricing.",
    conversation_state: "NEEDS_APPROVAL",
    needs_approval: true,
    latest_draft: inboxItem.latest_draft,
    latest_sales_run: null,
  },
  items: timelineItems,
  total_items: timelineItems.length,
};

function pageOf(
  items: InboxItem[],
  total = items.length,
  overrides: Partial<InboxListResponse> = {},
): InboxListResponse {
  return {
    items,
    limit: 20,
    offset: 0,
    total,
    state_counts: {
      OPEN: items.filter((item) => item.conversation_state === "OPEN").length,
      NEEDS_APPROVAL: items.filter(
        (item) => item.conversation_state === "NEEDS_APPROVAL",
      ).length,
      CLOSED: items.filter((item) => item.conversation_state === "CLOSED")
        .length,
    },
    needs_approval_count: items.filter((item) => item.needs_approval).length,
    ...overrides,
  };
}

describe("AI Inbox page", () => {
  beforeEach(() => {
    getInboxMock.mockReset();
    getInboxConversationMock.mockReset();
    getInboxMock.mockResolvedValue(pageOf([]));
    getInboxConversationMock.mockResolvedValue(conversation);
  });

  it("loads the inbox and shows empty state without channel copy", async () => {
    render(<InboxPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "AI Inbox" }),
    ).toBeVisible();
    expect(
      await screen.findByRole("heading", { name: "No conversations yet" }),
    ).toBeVisible();
    expect(screen.getByText(/website enquiries, drafts, email sends/i)).toBeVisible();
    expect(screen.queryByText(/WhatsApp/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/communication channels are connected/i)).not.toBeInTheDocument();
    expect(getInboxMock).toHaveBeenCalled();
  });

  it("shows error and retry for list failures", async () => {
    getInboxMock.mockRejectedValueOnce(new Error("network"));
    render(<InboxPage />);
    expect(
      await screen.findByRole("heading", { name: "Inbox could not be loaded" }),
    ).toBeVisible();
    getInboxMock.mockResolvedValueOnce(pageOf([]));
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "No conversations yet" }),
    ).toBeVisible();
  });

  it("renders summary counts from the list response", async () => {
    getInboxMock.mockResolvedValue(
      pageOf([inboxItem], 1, {
        state_counts: { OPEN: 2, NEEDS_APPROVAL: 1, CLOSED: 3 },
        needs_approval_count: 1,
      }),
    );
    render(<InboxPage />);
    expect(await screen.findByText("Ada Lovelace")).toBeVisible();
    const metricCards = screen.getAllByRole("article");
    expect(
      within(metricCards[0]).getByRole("heading", {
        name: "Open conversations",
      }),
    ).toBeVisible();
    expect(within(metricCards[0]).getByText("2")).toBeVisible();
    expect(within(metricCards[1]).getByText("1")).toBeVisible();
    expect(within(metricCards[2]).getByText("3")).toBeVisible();
    expect(within(metricCards[3]).getByText("1")).toBeVisible();
    expect(screen.queryByText("AI handled")).not.toBeInTheDocument();
  });

  it("renders conversation list rows from inbox items", async () => {
    getInboxMock.mockResolvedValue(pageOf([inboxItem]));
    render(<InboxPage />);
    const row = await screen.findByRole("button", { name: /Ada Lovelace/ });
    expect(within(row).getByText("Analytical Engines")).toBeVisible();
    expect(
      within(row).getByText("Thanks for writing — happy to share a demo slot."),
    ).toBeVisible();
    expect(within(row).getByText("Needs approval")).toBeVisible();
    expect(within(row).getByText("Needs review")).toBeVisible();
  });

  it("sends search, state, source, and needs-approval filters", async () => {
    const user = userEvent.setup();
    render(<InboxPage />);
    await screen.findByRole("heading", { name: "No conversations yet" });
    await user.type(
      screen.getByRole("searchbox", { name: "Search conversations" }),
      "Ada",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Conversation status" }),
      "NEEDS_APPROVAL",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Needs approval" }),
      "true",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Lead source" }),
      "WEBSITE",
    );
    await waitFor(() => {
      expect(getInboxMock).toHaveBeenCalledWith(
        expect.objectContaining({
          q: "Ada",
          conversation_state: "NEEDS_APPROVAL",
          needs_approval: true,
          source: "WEBSITE",
        }),
      );
    });
  });

  it("shows no-matching state when filters return empty", async () => {
    const user = userEvent.setup();
    render(<InboxPage />);
    await screen.findByRole("heading", { name: "No conversations yet" });
    getInboxMock.mockResolvedValue(pageOf([]));
    await user.type(
      screen.getByRole("searchbox", { name: "Search conversations" }),
      "zzz",
    );
    expect(
      await screen.findByRole("heading", { name: "No matching conversations" }),
    ).toBeVisible();
  });

  it("loads conversation detail, timeline, and lead context on select", async () => {
    getInboxMock.mockResolvedValue(pageOf([inboxItem]));
    render(<InboxPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: /Ada Lovelace/ }),
    );
    await waitFor(() =>
      expect(getInboxConversationMock).toHaveBeenCalledWith("lead-1"),
    );
    expect(
      await screen.findByRole("heading", { name: "Website enquiry" }),
    ).toBeVisible();
    expect(screen.getAllByText("Please call me about pricing.").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Draft generated")).toBeVisible();
    expect(screen.getByText("Draft body text")).toBeVisible();
    expect(screen.getByText("Email sent")).toBeVisible();
    expect(screen.getByText("Sent email body")).toBeVisible();
    expect(screen.getByText("Email failed")).toBeVisible();
    expect(screen.getByText("Failed email body")).toBeVisible();
    expect(screen.getByText("Follow-up email sent")).toBeVisible();
    expect(screen.getByText("Follow-up body")).toBeVisible();
    expect(screen.getByText("ada@example.com")).toBeVisible();
    expect(screen.getByText("+1 555 0100")).toBeVisible();
    expect(screen.getByRole("link", { name: "Open lead" })).toHaveAttribute(
      "href",
      "/leads/lead-1",
    );
    const draftEvent = screen.getByText("Draft generated").closest("li");
    expect(draftEvent).not.toBeNull();
    expect(within(draftEvent!).getByText("AI draft")).toBeVisible();
    expect(within(draftEvent!).queryByText("Message sent")).not.toBeInTheDocument();
    const sentEvent = screen.getByText("Email sent").closest("li");
    expect(within(sentEvent!).getByText("Message sent")).toBeVisible();
    const failedEvent = screen.getByText("Email failed").closest("li");
    expect(within(failedEvent!).getByText("Failed")).toBeVisible();
    expect(within(failedEvent!).queryByText("Message sent")).not.toBeInTheDocument();
  });

  it("keeps the composer disabled and exposes no send/approval actions", async () => {
    getInboxMock.mockResolvedValue(pageOf([inboxItem]));
    render(<InboxPage />);
    await userEvent.click(
      await screen.findByRole("button", { name: /Ada Lovelace/ }),
    );
    await screen.findByText("Draft generated");
    expect(screen.getByLabelText("Reply composer")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send reply" })).toBeDisabled();
    expect(
      screen.getByText(/Replies are not sent from Inbox/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /approve/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /^send$/i }),
    ).not.toBeInTheDocument();
  });

  it("provides mobile conversation and workspace navigation", async () => {
    const user = userEvent.setup();
    render(<InboxPage />);
    await screen.findByRole("heading", { name: "No conversations yet" });
    const conversationsButton = screen.getByRole("button", {
      name: "Conversations",
    });
    const workspaceButton = screen.getByRole("button", { name: "Workspace" });
    const conversationPane = document.querySelector("#inbox-conversation-list");
    const workspacePane = document.querySelector(
      "#inbox-conversation-workspace",
    );
    expect(conversationsButton).toHaveAttribute("aria-pressed", "true");
    expect(conversationPane).toHaveClass("block");
    expect(workspacePane).toHaveClass("hidden");
    await user.click(workspaceButton);
    expect(workspaceButton).toHaveAttribute("aria-pressed", "true");
    expect(conversationPane).toHaveClass("hidden");
    expect(workspacePane).toHaveClass("block");
    await user.click(
      screen.getByRole("button", { name: "Back to conversations" }),
    );
    expect(conversationsButton).toHaveAttribute("aria-pressed", "true");
  });

  it("paginates with next", async () => {
    getInboxMock.mockResolvedValue({
      ...pageOf([inboxItem], 21),
      total: 21,
    });
    render(<InboxPage />);
    expect(await screen.findByText("Showing 1–20 of 21")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => {
      expect(getInboxMock).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 20, limit: 20 }),
      );
    });
  });
});
