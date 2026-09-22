import { MessageSquareText } from "lucide-react";

import { formatTimestamp } from "@/components/agents/execution-status";
import { AiBadge } from "@/components/ai/ai-badge";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";
import type { InboxTimelineItem, InboxTimelineKind } from "@/types/api";

type ConversationTimelineProps = {
  items: InboxTimelineItem[];
};

const kindLabels: Record<InboxTimelineKind, string> = {
  LEAD_CREATED: "Lead created",
  WEBSITE_ENQUIRY: "Website enquiry",
  LEAD_STATUS_CHANGED: "Lead status changed",
  QUALIFICATION_COMPLETED: "Qualification completed",
  DRAFT_GENERATED: "Draft generated",
  DRAFT_EDITED: "Draft edited",
  DRAFT_APPROVED: "Approved draft",
  DRAFT_REJECTED: "Rejected draft",
  EMAIL_SENT: "Email sent",
  EMAIL_FAILED: "Email failed",
  FOLLOW_UP_SCHEDULED: "Follow-up scheduled",
  FOLLOW_UP_RESCHEDULED: "Follow-up rescheduled",
  FOLLOW_UP_COMPLETED: "Follow-up completed",
  FOLLOW_UP_CANCELLED: "Follow-up cancelled",
  FOLLOW_UP_EXECUTION_SENT: "Follow-up email sent",
  FOLLOW_UP_EXECUTION_FAILED: "Follow-up email failed",
  SALES_RUN_STARTED: "Sales Agent started",
  SALES_RUN_WAITING_APPROVAL: "Waiting for review",
  SALES_RUN_COMPLETED: "Sales Run completed",
  SALES_RUN_CANCELLED: "Sales Run cancelled",
  SALES_RUN_FAILED: "Sales Run failed",
};

const directionLabels = {
  inbound: "Customer",
  outbound: "Outbound",
  internal: "Internal",
} as const;

function kindBadge(item: InboxTimelineItem): { status: StatusValue; label: string } {
  if (item.kind === "EMAIL_FAILED" || item.kind === "FOLLOW_UP_EXECUTION_FAILED") {
    return { status: "failed", label: "Failed" };
  }
  if (item.is_sent_message) {
    return { status: "success", label: "Sent" };
  }
  if (item.is_draft) {
    if (item.kind === "DRAFT_APPROVED") {
      return { status: "success", label: "AI draft" };
    }
    if (item.kind === "DRAFT_REJECTED") {
      return { status: "failed", label: "AI draft" };
    }
    return { status: "draft", label: "AI draft" };
  }
  if (item.direction === "inbound") {
    return { status: "pending", label: "Customer" };
  }
  return { status: "draft", label: directionLabels[item.direction] };
}

export function ConversationTimeline({ items }: ConversationTimelineProps) {
  if (items.length === 0) {
    return (
      <EmptyState
        compact
        icon={<MessageSquareText />}
        className="max-w-none rounded-none border-0 shadow-none"
        title="No timeline events yet"
        description="Activity for this lead will appear here as drafts, emails, Sales Runs, and follow-ups are recorded."
      />
    );
  }

  return (
    <ol
      aria-label="Conversation timeline"
      className="grid gap-3 p-4 sm:p-5"
      data-slot="conversation-timeline"
    >
      {items.map((item) => {
        const badge = kindBadge(item);
        return (
          <li
            key={item.id}
            className={cn(
              "border-border bg-card rounded-lg border p-4",
              item.direction === "inbound" && "border-l-info border-l-4",
              item.direction === "outbound" &&
                item.is_sent_message &&
                "border-l-success border-l-4",
              item.direction === "outbound" &&
                !item.is_sent_message &&
                "border-l-destructive border-l-4",
              item.direction === "internal" && "border-l-border border-l-4",
            )}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={badge.status} label={badge.label} />
                {item.is_draft ? <AiBadge label="Generated" /> : null}
                {item.kind === "EMAIL_SENT" ||
                item.kind === "FOLLOW_UP_EXECUTION_SENT" ? (
                  <StatusBadge status="success" label="Message sent" />
                ) : null}
              </div>
              <time
                className="text-muted-foreground text-xs"
                dateTime={item.occurred_at}
              >
                {formatTimestamp(item.occurred_at) ?? "—"}
              </time>
            </div>
            <h4 className="mt-3 text-sm font-medium leading-6">
              {kindLabels[item.kind] ?? item.title}
            </h4>
            {item.summary ? (
              <p className="text-muted-foreground mt-1 text-xs leading-5">
                {item.summary}
              </p>
            ) : null}
            {item.body ? (
              <p
                className={cn(
                  "mt-3 whitespace-pre-wrap text-sm leading-6",
                  item.is_draft && "text-muted-foreground italic",
                )}
              >
                {item.body}
              </p>
            ) : null}
            {item.status ? (
              <p className="text-muted-foreground mt-2 text-xs">
                Status: {item.status}
              </p>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
