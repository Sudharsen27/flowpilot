import { MessageSquareText } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";

export type ConversationStatus = "open" | "waiting" | "resolved";
export type ConversationHandling = "ai" | "human" | "unassigned";

export type ConversationListItem = {
  id: string;
  contactName: string;
  company?: string;
  status: ConversationStatus;
  lastMessagePreview?: string;
  timeLabel?: string;
  handling: ConversationHandling;
};

type ConversationListProps = {
  conversations: ConversationListItem[];
  selectedId?: string;
  onSelect?: (conversation: ConversationListItem) => void;
};

const statusPresentation: Record<
  ConversationStatus,
  { status: StatusValue; label: string }
> = {
  open: { status: "active", label: "Open" },
  waiting: { status: "warning", label: "Waiting" },
  resolved: { status: "success", label: "Resolved" },
};

const handlingPresentation: Record<
  ConversationHandling,
  { status: StatusValue; label: string }
> = {
  ai: { status: "pending", label: "AI handled" },
  human: { status: "active", label: "Human handled" },
  unassigned: { status: "draft", label: "Unassigned" },
};

export function ConversationList({
  conversations,
  selectedId,
  onSelect,
}: ConversationListProps) {
  if (conversations.length === 0) {
    return (
      <EmptyState
        compact
        icon={<MessageSquareText />}
        className="max-w-none rounded-none border-x-0 border-b-0 shadow-none"
        title="No conversations yet"
        description="Conversations will appear here after customer communication channels are connected and begin sending messages to FlowPilot."
      />
    );
  }

  return (
    <ul
      aria-label="Conversations"
      className="divide-border divide-y"
      data-slot="conversation-list"
    >
      {conversations.map((conversation) => {
        const status = statusPresentation[conversation.status];
        const handling = handlingPresentation[conversation.handling];
        const isSelected = selectedId === conversation.id;

        return (
          <li key={conversation.id}>
            <button
              type="button"
              className={cn(
                "hover:bg-surface-subtle focus-visible:ring-ring/40 w-full p-4 text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-inset",
                isSelected && "bg-surface-subtle",
              )}
              aria-pressed={isSelected}
              onClick={() => onSelect?.(conversation)}
            >
              <span className="flex items-start justify-between gap-3">
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">
                    {conversation.contactName}
                  </span>
                  {conversation.company ? (
                    <span className="text-muted-foreground mt-0.5 block truncate text-xs">
                      {conversation.company}
                    </span>
                  ) : null}
                </span>
                {conversation.timeLabel ? (
                  <span className="text-muted-foreground shrink-0 text-xs">
                    {conversation.timeLabel}
                  </span>
                ) : null}
              </span>
              {conversation.lastMessagePreview ? (
                <span className="text-muted-foreground mt-3 block truncate text-sm">
                  {conversation.lastMessagePreview}
                </span>
              ) : null}
              <span className="mt-3 flex flex-wrap gap-2">
                <StatusBadge status={status.status} label={status.label} />
                <StatusBadge status={handling.status} label={handling.label} />
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
