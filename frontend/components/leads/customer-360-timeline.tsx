import { MessageSquareText } from "lucide-react";

import { ConversationTimeline } from "@/components/ai-inbox/conversation-timeline";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { InboxTimelineItem } from "@/types/api";

type Customer360TimelineProps = {
  items?: InboxTimelineItem[];
  totalItems?: number;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
};

export function Customer360Timeline({
  items = [],
  totalItems,
  loading = false,
  error = null,
  onRetry,
}: Customer360TimelineProps) {
  const count = totalItems ?? items.length;

  return (
    <section
      className="bg-card border-border flex min-h-[28rem] min-w-0 flex-col overflow-hidden rounded-lg border motion-safe:transition-shadow"
      aria-labelledby="customer-360-timeline-title"
    >
      <header className="border-border flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className="bg-muted text-muted-foreground flex size-8 shrink-0 items-center justify-center rounded-md"
            aria-hidden="true"
          >
            <MessageSquareText className="size-4" />
          </span>
          <div className="min-w-0">
            <h2
              id="customer-360-timeline-title"
              className="text-sm font-semibold tracking-tight"
            >
              Conversation timeline
            </h2>
            <p className="text-muted-foreground text-xs">
              Customer journey: enquiry, AI work, human decisions, and outbound
              email.
            </p>
          </div>
        </div>
        {!loading && !error ? (
          <p className="text-muted-foreground text-xs" aria-live="polite">
            {count} event{count === 1 ? "" : "s"}
          </p>
        ) : null}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {error ? (
          <div className="p-4">
            <StatePanel
              kind="error"
              className="max-w-none"
              title="Unable to load conversation history"
              description="The conversation timeline could not be loaded. Customer profile and AI insights remain available."
              action={
                onRetry ? (
                  <Button type="button" variant="outline" onClick={onRetry}>
                    Retry
                  </Button>
                ) : null
              }
            />
          </div>
        ) : loading ? (
          <div className="grid gap-3 p-4" role="status">
            <Skeleton className="h-28 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-28 w-full" />
            <span className="sr-only">Loading conversation timeline</span>
          </div>
        ) : (
          <ConversationTimeline
            items={items}
            emptyTitle="No conversation activity yet"
            emptyDescription="Website enquiries, AI drafts, approvals, emails, and follow-ups will appear here as they are recorded."
          />
        )}
      </div>
    </section>
  );
}
