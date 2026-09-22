import Link from "next/link";
import {
  ArrowLeft,
  Bot,
  MessageSquareText,
  Send,
  UserRound,
  UserRoundCheck,
} from "lucide-react";

import { ConversationTimeline } from "@/components/ai-inbox/conversation-timeline";
import { AiBadge } from "@/components/ai/ai-badge";
import { DetailRow } from "@/components/data-display/detail-row";
import { StatePanel } from "@/components/data-display/state-panel";
import { Label } from "@/components/forms/label";
import { Textarea } from "@/components/forms/textarea";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { RelativeTime } from "@/components/ui/relative-time";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  draftReviewLabels,
  inboxSourceLabels,
  inboxStateLabels,
} from "@/lib/inbox-labels";
import type { InboxConversationResponse } from "@/types/api";

type ConversationWorkspaceProps = {
  conversation: InboxConversationResponse | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onBack?: () => void;
};

export function ConversationWorkspace({
  conversation,
  loading = false,
  error = null,
  onRetry,
  onBack,
}: ConversationWorkspaceProps) {
  const lead = conversation?.lead;

  return (
    <Card
      as="section"
      className="flex min-h-[42rem] min-w-0 flex-col overflow-hidden motion-safe:transition-shadow"
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
              className="text-base font-semibold tracking-tight"
            >
              {lead?.name ?? "Conversation workspace"}
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              {lead
                ? [
                    lead.company,
                    lead.email,
                    inboxStateLabels[lead.conversation_state],
                  ]
                    .filter(Boolean)
                    .join(" · ")
                : "Select a customer to review enquiry history, AI activity, and decisions."}
            </p>
          </div>
        </div>
        {lead ? (
          <StatusBadge
            status={
              lead.needs_approval
                ? "warning"
                : lead.conversation_state === "CLOSED"
                  ? "success"
                  : "active"
            }
            label={
              lead.needs_approval
                ? "Needs your review"
                : inboxStateLabels[lead.conversation_state]
            }
          />
        ) : (
          <StatusBadge status="draft" label="No selection" />
        )}
      </header>

      <div className="grid min-h-0 flex-1 xl:grid-cols-[minmax(0,1fr)_minmax(16rem,19rem)]">
        <div className="flex min-h-[30rem] min-w-0 flex-col">
          <section
            className="min-h-0 flex-1 overflow-y-auto"
            aria-labelledby="message-timeline-title"
          >
            <div className="border-border flex items-center justify-between gap-3 border-b px-4 py-3 sm:px-5">
              <h4
                id="message-timeline-title"
                className="text-sm font-medium tracking-tight"
              >
                Timeline
              </h4>
              {conversation ? (
                <p className="text-muted-foreground text-xs">
                  {conversation.total_items} event
                  {conversation.total_items === 1 ? "" : "s"}
                </p>
              ) : null}
            </div>
            {error ? (
              <div className="p-4">
                <StatePanel
                  kind="error"
                  title="Unable to load conversation"
                  description={error}
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
                <Skeleton className="h-28" />
                <Skeleton className="h-24" />
                <Skeleton className="h-28" />
                <span className="sr-only">Loading conversation</span>
              </div>
            ) : !conversation ? (
              <div className="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center">
                <div
                  className="bg-muted text-muted-foreground flex size-10 items-center justify-center rounded-lg"
                  aria-hidden="true"
                >
                  <MessageSquareText className="size-5" />
                </div>
                <p className="mt-4 text-sm font-medium">No conversation selected</p>
                <p className="text-muted-foreground mt-1.5 max-w-sm text-sm leading-6">
                  Choose a customer from the list to see what they asked, what
                  FlowPilot prepared, and what still needs a human decision.
                </p>
              </div>
            ) : (
              <ConversationTimeline items={conversation.items} />
            )}
          </section>

          <footer className="border-border bg-surface-subtle border-t p-4">
            <Label htmlFor="reply-composer">Reply composer</Label>
            <Textarea
              id="reply-composer"
              className="mt-2 min-h-20 resize-none"
              placeholder="Replies are not sent from Inbox."
              disabled
              aria-describedby="reply-composer-help"
            />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <p
                id="reply-composer-help"
                className="text-muted-foreground text-xs"
              >
                Replies are not sent from Inbox. Approve and send from the Lead
                or Sales Agent.
              </p>
              <Button type="button" disabled>
                <Send aria-hidden="true" />
                Send reply
              </Button>
            </div>
          </footer>
        </div>

        <aside
          className="border-border bg-surface-subtle/60 grid content-start gap-3 border-t p-4 xl:border-t-0 xl:border-l"
          aria-label="Customer context"
        >
          <section
            className="bg-card border-border rounded-lg border p-4"
            aria-labelledby="customer-profile-title"
          >
            <div className="flex items-center gap-2">
              <UserRound
                className="text-muted-foreground size-4"
                aria-hidden="true"
              />
              <h4 id="customer-profile-title" className="text-sm font-medium">
                Customer
              </h4>
            </div>
            {loading && !lead ? (
              <div className="mt-3 grid gap-2" role="status">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-4/5" />
                <span className="sr-only">Loading customer context</span>
              </div>
            ) : lead ? (
              <div className="mt-3 grid gap-4">
                <div>
                  <p className="text-base font-semibold tracking-tight">
                    {lead.name}
                  </p>
                  <p className="text-muted-foreground mt-1 text-sm">
                    {lead.company ?? "No company on file"}
                  </p>
                </div>
                <dl className="grid gap-2.5">
                  <DetailRow
                    label="Email"
                    value={lead.email ?? "—"}
                    muted={!lead.email}
                  />
                  <DetailRow
                    label="Phone"
                    value={lead.phone ?? "—"}
                    muted={!lead.phone}
                  />
                  <DetailRow
                    label="Lead status"
                    value={<LeadStatusBadge status={lead.lead_status} />}
                  />
                  <DetailRow
                    label="Source"
                    value={inboxSourceLabels[lead.source]}
                  />
                  <DetailRow
                    label="Conversation"
                    value={inboxStateLabels[lead.conversation_state]}
                  />
                </dl>
              </div>
            ) : (
              <p className="text-muted-foreground mt-2 text-xs leading-5">
                Contact details appear when a conversation is selected.
              </p>
            )}
          </section>

          {lead?.enquiry ? (
            <section
              className="bg-card border-border rounded-lg border p-4"
              aria-labelledby="enquiry-title"
            >
              <h4 id="enquiry-title" className="text-sm font-medium">
                What they want
              </h4>
              <p className="text-muted-foreground mt-2 text-sm leading-6 whitespace-pre-wrap">
                {lead.enquiry}
              </p>
            </section>
          ) : null}

          <section
            className="bg-card border-border rounded-lg border p-4"
            aria-labelledby="attention-title"
          >
            <div className="flex items-center gap-2">
              <UserRoundCheck
                className="text-muted-foreground size-4"
                aria-hidden="true"
              />
              <h4 id="attention-title" className="text-sm font-medium">
                Attention
              </h4>
            </div>
            {lead?.needs_approval ? (
              <div className="border-warning/30 bg-warning/10 mt-3 rounded-md border px-3 py-2.5">
                <p className="text-warning-text text-sm font-medium">
                  Needs your review
                </p>
                <p className="text-muted-foreground mt-1 text-xs leading-5">
                  An AI draft or Sales Run is waiting. Approve and send from the
                  Lead or Sales Agent workspace — not from Inbox.
                </p>
              </div>
            ) : (
              <p className="text-muted-foreground mt-2 text-xs leading-5">
                No approval required right now. Inbox stays read-only.
              </p>
            )}
          </section>

          {(lead?.latest_draft || lead?.latest_sales_run) && (
            <section
              className="bg-card border-border rounded-lg border p-4"
              aria-labelledby="flowpilot-activity-title"
            >
              <div className="flex items-center gap-2">
                <Bot className="text-ai-text size-4" aria-hidden="true" />
                <h4 id="flowpilot-activity-title" className="text-sm font-medium">
                  FlowPilot activity
                </h4>
              </div>
              <dl className="mt-3 grid gap-3">
                {lead.latest_draft ? (
                  <div className="border-ai-border bg-ai/5 rounded-md border px-3 py-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <AiBadge label="Generated" />
                      <span className="text-xs font-medium">
                        {lead.latest_draft.review_status
                          ? draftReviewLabels[lead.latest_draft.review_status]
                          : lead.latest_draft.status}
                      </span>
                    </div>
                    <p className="text-muted-foreground mt-1.5 text-xs">
                      AI draft · not automatically sent
                    </p>
                    <RelativeTime
                      value={lead.latest_draft.created_at}
                      className="mt-1 block"
                    />
                  </div>
                ) : null}
                {lead.latest_sales_run ? (
                  <DetailRow
                    label="Sales Run"
                    value={`${lead.latest_sales_run.status.replaceAll("_", " ")} · ${lead.latest_sales_run.stage}`}
                  />
                ) : null}
              </dl>
            </section>
          )}

          {lead ? (
            <div className="px-1">
              <Link
                href={`/leads/${lead.lead_id}`}
                className="text-foreground text-sm font-medium underline-offset-4 hover:underline"
              >
                Open full lead record
              </Link>
            </div>
          ) : null}
        </aside>
      </div>
    </Card>
  );
}
