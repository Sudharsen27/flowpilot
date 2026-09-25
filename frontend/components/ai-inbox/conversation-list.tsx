import type { ReactNode } from "react";
import { MessageSquareText } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { RelativeTime } from "@/components/ui/relative-time";
import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import { inboxSourceLabels } from "@/lib/inbox-labels";
import { cn } from "@/lib/utils";
import type { LeadSource } from "@/types/api";

export type ConversationStatus = "open" | "waiting" | "resolved";

export type ConversationListItem = {
  id: string;
  contactName: string;
  company?: string;
  source?: LeadSource;
  status: ConversationStatus;
  lastMessagePreview?: string;
  occurredAt?: string;
  needsApproval: boolean;
};

type ConversationListProps = {
  conversations: ConversationListItem[];
  selectedId?: string;
  onSelect?: (conversation: ConversationListItem) => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
};

const statusPresentation: Record<
  ConversationStatus,
  { status: StatusValue; label: string }
> = {
  open: { status: "active", label: "Open" },
  waiting: { status: "warning", label: "Needs your review" },
  resolved: { status: "success", label: "Closed" },
};

export function ConversationList({
  conversations,
  selectedId,
  onSelect,
  emptyTitle = "No customer conversations yet",
  emptyDescription = "When website enquiries, AI-assisted sales activity, or customer communication appear, they'll show up here.",
  emptyAction,
}: ConversationListProps) {
  if (conversations.length === 0) {
    return (
      <EmptyState
        compact
        icon={<MessageSquareText />}
        className="max-w-none rounded-none border-x-0 border-b-0 shadow-none"
        title={emptyTitle}
        description={emptyDescription}
        action={emptyAction}
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
        const isSelected = selectedId === conversation.id;
        const showStatusBadge =
          conversation.needsApproval || conversation.status !== "open";

        return (
          <li key={conversation.id}>
            <button
              type="button"
              className={cn(
                "hover:bg-surface-subtle focus-visible:ring-ring/40 motion-safe:transition-colors w-full p-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-inset",
                isSelected && "bg-surface-subtle",
                conversation.needsApproval &&
                  !isSelected &&
                  "border-l-warning bg-warning/5 border-l-2",
                isSelected && conversation.needsApproval &&
                  "border-l-warning bg-warning/5 border-l-2",
              )}
              aria-pressed={isSelected}
              aria-current={isSelected ? "true" : undefined}
              title={
                conversation.occurredAt
                  ? `${conversation.contactName} · ${conversation.occurredAt}`
                  : conversation.contactName
              }
              onClick={() => onSelect?.(conversation)}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="text-foreground block truncate text-sm font-semibold tracking-tight">
                      {conversation.contactName}
                    </span>
                    {conversation.needsApproval ? (
                      <StatusBadge
                        status="warning"
                        label="Review"
                        className="shrink-0"
                      />
                    ) : null}
                  </div>
                  <div className="text-muted-foreground mt-1 flex min-w-0 flex-wrap items-center gap-1.5 text-[11px] leading-5">
                    {conversation.company ? (
                      <span className="truncate">{conversation.company}</span>
                    ) : (
                      <span className="truncate italic">No company</span>
                    )}
                    {conversation.source ? (
                      <>
                        <span aria-hidden="true">•</span>
                        <span className="shrink-0">
                          {inboxSourceLabels[conversation.source]}
                        </span>
                      </>
                    ) : null}
                  </div>
                </div>
                {conversation.occurredAt ? (
                  <RelativeTime
                    value={conversation.occurredAt}
                    className="shrink-0 text-right"
                  />
                ) : null}
              </div>

              <div className="mt-3 flex items-start gap-2">
                <div
                  className={cn(
                    "min-w-0 flex-1 rounded-md border px-2.5 py-2 text-sm leading-5",
                    conversation.needsApproval
                      ? "border-warning/25 bg-warning/5 text-foreground"
                      : "border-border bg-muted/30 text-muted-foreground",
                  )}
                >
                  {conversation.lastMessagePreview ? (
                    <span className="line-clamp-2 block">
                      {conversation.lastMessagePreview}
                    </span>
                  ) : (
                    <span className="italic">No preview yet</span>
                  )}
                </div>
              </div>

              {showStatusBadge ? (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                  <StatusBadge status={status.status} label={status.label} />
                  {conversation.needsApproval ? (
                    <span className="text-warning-text text-[11px] font-medium uppercase tracking-[0.08em]">
                      Human review
                    </span>
                  ) : null}
                </div>
              ) : null}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
