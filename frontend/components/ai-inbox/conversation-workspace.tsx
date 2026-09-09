import {
  ArrowLeft,
  Bot,
  MessageSquareText,
  Send,
  UserRound,
  UserRoundCheck,
} from "lucide-react";

import { Label } from "@/components/forms/label";
import { Textarea } from "@/components/forms/textarea";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

type ConversationWorkspaceProps = {
  onBack?: () => void;
};

export function ConversationWorkspace({ onBack }: ConversationWorkspaceProps) {
  return (
    <Card
      as="section"
      className="flex min-h-[42rem] min-w-0 flex-col overflow-hidden"
      aria-labelledby="conversation-workspace-title"
    >
      <header className="border-border flex flex-wrap items-start justify-between gap-3 border-b px-4 py-4 sm:px-5">
        <div className="flex min-w-0 items-start gap-2">
          {onBack ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="Back to conversations"
              onClick={onBack}
            >
              <ArrowLeft aria-hidden="true" />
            </Button>
          ) : null}
          <div className="min-w-0">
            <h3
              id="conversation-workspace-title"
              className="text-base font-medium tracking-tight"
            >
              Conversation workspace
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Select a connected conversation to review its context and
              messages.
            </p>
          </div>
        </div>
        <StatusBadge status="draft" label="Unavailable" />
      </header>

      <div className="grid min-h-0 flex-1 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="flex min-h-[30rem] min-w-0 flex-col">
          <section
            className="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center"
            aria-labelledby="message-timeline-title"
          >
            <div
              className="bg-muted text-muted-foreground flex size-10 items-center justify-center rounded-lg"
              aria-hidden="true"
            >
              <MessageSquareText className="size-5" />
            </div>
            <h4
              id="message-timeline-title"
              className="mt-4 text-sm font-medium"
            >
              No conversation selected
            </h4>
            <p className="text-muted-foreground mt-1.5 max-w-sm text-sm leading-6">
              The message timeline will appear here when conversation channels
              are connected and a real conversation is selected.
            </p>
          </section>

          <footer className="border-border bg-surface-subtle border-t p-4">
            <Label htmlFor="reply-composer">Reply composer</Label>
            <Textarea
              id="reply-composer"
              className="mt-2 min-h-20 resize-none"
              placeholder="Replying becomes available with a connected messaging channel."
              disabled
              aria-describedby="reply-composer-help"
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <p
                id="reply-composer-help"
                className="text-muted-foreground text-xs"
              >
                Sending messages is not configured.
              </p>
              <Button type="button" disabled>
                <Send aria-hidden="true" />
                Send reply
              </Button>
            </div>
          </footer>
        </div>

        <aside
          className="border-border bg-surface-subtle/60 grid content-start gap-4 border-t p-4 xl:border-t-0 xl:border-l"
          aria-label="Conversation context and assistance"
        >
          <section
            className="bg-card border-border rounded-lg border p-4"
            aria-labelledby="customer-context-title"
          >
            <div className="flex items-center gap-2">
              <UserRound
                className="text-muted-foreground size-4"
                aria-hidden="true"
              />
              <h4 id="customer-context-title" className="text-sm font-medium">
                Customer context
              </h4>
            </div>
            <p className="text-muted-foreground mt-2 text-xs leading-5">
              Contact and company details will appear only for a real connected
              conversation.
            </p>
          </section>

          <section
            className="bg-card border-border rounded-lg border p-4"
            aria-labelledby="ai-assistance-title"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Bot
                  className="text-muted-foreground size-4"
                  aria-hidden="true"
                />
                <h4 id="ai-assistance-title" className="text-sm font-medium">
                  AI assistance
                </h4>
              </div>
              <StatusBadge status="draft" label="Unavailable" />
            </div>
            <p className="text-muted-foreground mt-2 text-xs leading-5">
              Suggested replies, summaries, and qualification context will
              appear here after AI assistance is implemented and conversations
              are connected.
            </p>
          </section>

          <section
            className="bg-card border-border rounded-lg border p-4"
            aria-labelledby="human-handoff-title"
          >
            <div className="flex items-center gap-2">
              <UserRoundCheck
                className="text-muted-foreground size-4"
                aria-hidden="true"
              />
              <h4 id="human-handoff-title" className="text-sm font-medium">
                Human handoff
              </h4>
            </div>
            <p className="text-muted-foreground mt-2 text-xs leading-5">
              Conversations requiring human attention can be surfaced here once
              assignment and escalation workflows are available.
            </p>
          </section>
        </aside>
      </div>
    </Card>
  );
}
