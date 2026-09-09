import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import InboxPage from "@/app/(app)/inbox/page";
import {
  ConversationList,
  type ConversationListItem,
} from "@/components/ai-inbox/conversation-list";

describe("AI Inbox page", () => {
  it("renders the page hierarchy and honest unavailable summary", () => {
    render(<InboxPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "AI Inbox" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { level: 2, name: "Inbox summary" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { level: 2, name: "Inbox workspace" }),
    ).toBeVisible();

    const metricCards = screen.getAllByRole("article");
    const metricLabels = [
      "Open conversations",
      "Waiting for response",
      "AI handled",
      "Needs human attention",
    ];
    expect(metricCards).toHaveLength(metricLabels.length);
    metricLabels.forEach((label, index) => {
      expect(
        within(metricCards[index]).getByRole("heading", {
          level: 3,
          name: label,
        }),
      ).toBeVisible();
    });
    expect(screen.getAllByText("—")).toHaveLength(4);
  });

  it("provides accessible, locally resettable conversation filters", async () => {
    const user = userEvent.setup();
    render(<InboxPage />);

    const search = screen.getByRole("searchbox", {
      name: "Search conversations",
    });
    const status = screen.getByRole("combobox", {
      name: "Conversation status",
    });
    const handling = screen.getByRole("combobox", {
      name: "Conversation handling",
    });
    const channel = screen.getByRole("combobox", {
      name: "Conversation channel",
    });

    await user.type(search, "Example");
    await user.selectOptions(status, "waiting");
    await user.selectOptions(handling, "human");
    await user.selectOptions(channel, "chat");
    await user.click(screen.getByRole("button", { name: "Clear filters" }));

    expect(search).toHaveValue("");
    expect(status).toHaveValue("all");
    expect(handling).toHaveValue("all");
    expect(channel).toHaveValue("all");
  });

  it("shows honest setup states without conversations or messages", () => {
    render(<InboxPage />);

    expect(
      screen.getByRole("heading", { name: "No conversations yet" }),
    ).toBeVisible();
    expect(
      screen.getByText(/communication channels are connected/),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "No conversation selected" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "AI assistance" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Human handoff" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Reply composer")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send reply" })).toBeDisabled();
    expect(
      screen.queryByRole("list", { name: "Conversations" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Example")).not.toBeInTheDocument();
  });

  it("provides clear mobile workspace and back navigation", async () => {
    const user = userEvent.setup();
    render(<InboxPage />);

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
    expect(conversationPane).toHaveClass("block");
    expect(workspacePane).toHaveClass("hidden");
  });

  it("renders accessible conversation rows when real data is supplied", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const conversation: ConversationListItem = {
      id: "conversation-1",
      contactName: "Test contact",
      company: "Test company",
      status: "open",
      lastMessagePreview: "Test message preview",
      timeLabel: "Test time",
      handling: "ai",
    };

    render(
      <ConversationList
        conversations={[conversation]}
        selectedId={conversation.id}
        onSelect={onSelect}
      />,
    );

    const row = screen.getByRole("button", { name: /Test contact/ });
    expect(screen.getByRole("list", { name: "Conversations" })).toBeVisible();
    expect(row).toHaveAttribute("aria-pressed", "true");
    expect(within(row).getByText("Open")).toBeVisible();
    expect(within(row).getByText("AI handled")).toBeVisible();

    await user.click(row);
    expect(onSelect).toHaveBeenCalledWith(conversation);
  });
});
