import Link from "next/link";
import {
  ArrowLeft,
  MessageSquareText,
  Send,
  UserRound,
  UserRoundCheck,
} from "lucide-react";

import { ConversationTimeline } from "@/components/ai-inbox/conversation-timeline";
import { formatTimestamp } from "@/components/agents/execution-status";
import { DetailRow } from "@/components/data-display/detail-row";
import { StatePanel } from "@/components/data-display/state-panel";
import { Label } from "@/components/forms/label";
import { Textarea } from "@/components/forms/textarea";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import type { InboxConversationResponse } from "@/types/api";

type ConversationWorkspaceProps = {
  conversation: InboxConversationResponse | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onBack?: () => void;
};

const sourceLabels = {
  MANUAL: "Manual",
  WEBSITE: "Website",
  EMAIL: "Email",
  CHAT: "Chat",
  API: "API",
  IMPORT: "Import",
} as const;

const stateLabels = {
  OPEN: "Open",
  NEEDS_APPROVAL: "Needs approval",
  CLOSED: "Closed",
} as const;

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
              {lead?.name ?? "Conversation workspace"}
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              {lead
                ? [
                    lead.email,
                    lead.company,
                    stateLabels[lead.conversation_state],
                  ]
                    .filter(Boolean)
                    .join(" · ")
                : "Select a conversation to review its timeline and lead context."}
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
                ? "Needs review"
                : stateLabels[lead.conversation_state]
            }
          />
        ) : (
          <StatusBadge status="draft" label="No selection" />
        )}
      </header>

      <div className="grid min-h-0 flex-1 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="flex min-h-[30rem] min-w-0 flex-col">
          <section
            className="min-h-0 flex-1 overflow-y-auto"
            aria-labelledby="message-timeline-title"
          >
            <h4 id="message-timeline-title" className="sr-only">
              Conversation timeline
            </h4>
            {error ? (
              <div className="p-4">
                <StatePanel
                  kind="error"
                  title="Conversation could not be loaded"
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
                  Choose a lead from the conversation list to inspect its
                  enquiry, drafts, emails, and follow-up history.
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
          className="border-border bg-surface-subtle/60 grid content-start gap-4 border-t p-4 xl:border-t-0 xl:border-l"
          aria-label="Conversation context"
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
            {loading && !lead ? (
              <div className="mt-3 grid gap-2" role="status">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
                <span className="sr-only">Loading customer context</span>
              </div>
            ) : lead ? (
              <dl className="mt-3 grid gap-3">
                <DetailRow label="Name" value={lead.name} />
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
                  label="Company"
                  value={lead.company ?? "—"}
                  muted={!lead.company}
                />
                <DetailRow
                  label="Lead status"
                  value={<LeadStatusBadge status={lead.lead_status} />}
                />
                <DetailRow label="Source" value={sourceLabels[lead.source]} />
                <DetailRow
                  label="Conversation"
                  value={stateLabels[lead.conversation_state]}
                />
                <DetailRow
                  label="Approval"
                  value={
                    lead.needs_approval ? (
                      <StatusBadge status="warning" label="Required" />
                    ) : (
                      "Not required"
                    )
                  }
                />
                <DetailRow
                  label="Enquiry"
                  value={lead.enquiry ?? "—"}
                  muted={!lead.enquiry}
                />
                {lead.latest_draft ? (
                  <DetailRow
                    label="Latest draft"
                    value={`${lead.latest_draft.review_status ?? lead.latest_draft.status} · ${formatTimestamp(lead.latest_draft.created_at) ?? ""}`}
                  />
                ) : null}
                {lead.latest_sales_run ? (
                  <DetailRow
                    label="Sales Run"
                    value={`${lead.latest_sales_run.status} · ${lead.latest_sales_run.stage}`}
                  />
                ) : null}
                <DetailRow
                  label="Lead record"
                  value={
                    <Link
                      href={`/leads/${lead.lead_id}`}
                      className="text-foreground underline-offset-4 hover:underline"
                    >
                      Open lead
                    </Link>
                  }
                />
              </dl>
            ) : (
              <p className="text-muted-foreground mt-2 text-xs leading-5">
                Contact and company details appear when a conversation is
                selected.
              </p>
            )}
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
                Human review
              </h4>
            </div>
            <p className="text-muted-foreground mt-2 text-xs leading-5">
              {lead?.needs_approval
                ? "This conversation needs approval before an email can be sent. Review and approve from the Lead or Sales Agent workspace."
                : "Inbox is read-only. Approve drafts and send email from the Lead or Sales Agent workspace."}
            </p>
          </section>
        </aside>
      </div>
    </Card>
  );
}
