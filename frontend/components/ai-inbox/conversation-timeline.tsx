import {
  Bot,
  CalendarClock,
  CheckCheck,
  Mail,
  MessageSquareText,
  UserRound,
} from "lucide-react";

import { AiBadge } from "@/components/ai/ai-badge";
import { EmptyState } from "@/components/empty-state";
import { RelativeTime } from "@/components/ui/relative-time";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";
import type {
  ActivityActorType,
  InboxTimelineItem,
  InboxTimelineKind,
} from "@/types/api";

type ConversationTimelineProps = {
  items: InboxTimelineItem[];
};

type TimelineLane =
  | "customer"
  | "ai"
  | "human"
  | "outbound"
  | "automation"
  | "system";

const kindLabels: Record<InboxTimelineKind, string> = {
  LEAD_CREATED: "Lead created",
  WEBSITE_ENQUIRY: "Website enquiry",
  LEAD_STATUS_CHANGED: "Lead status changed",
  QUALIFICATION_COMPLETED: "AI qualification",
  DRAFT_GENERATED: "AI-generated response",
  DRAFT_EDITED: "Draft edited",
  DRAFT_APPROVED: "Draft approved",
  DRAFT_REJECTED: "Draft rejected",
  EMAIL_SENT: "Email sent",
  EMAIL_FAILED: "Email could not be delivered",
  FOLLOW_UP_SCHEDULED: "Follow-up scheduled",
  FOLLOW_UP_RESCHEDULED: "Follow-up rescheduled",
  FOLLOW_UP_COMPLETED: "Follow-up completed",
  FOLLOW_UP_CANCELLED: "Follow-up cancelled",
  FOLLOW_UP_EXECUTION_SENT: "Follow-up email sent",
  FOLLOW_UP_EXECUTION_FAILED: "Follow-up email failed",
  SALES_RUN_STARTED: "Sales Agent started",
  SALES_RUN_WAITING_APPROVAL: "Waiting for your review",
  SALES_RUN_COMPLETED: "Sales Run completed",
  SALES_RUN_CANCELLED: "Sales Run cancelled",
  SALES_RUN_FAILED: "Sales Run failed",
};

const actorLabels: Record<ActivityActorType, string> = {
  USER: "Team member",
  AGENT: "Sales Agent",
  SYSTEM: "System",
  PUBLIC_VISITOR: "Website visitor",
};

function laneFor(item: InboxTimelineItem): TimelineLane {
  if (item.kind === "WEBSITE_ENQUIRY") return "customer";
  if (
    item.kind === "EMAIL_SENT" ||
    item.kind === "EMAIL_FAILED" ||
    item.kind === "FOLLOW_UP_EXECUTION_SENT" ||
    item.kind === "FOLLOW_UP_EXECUTION_FAILED"
  ) {
    return "outbound";
  }
  if (
    item.kind === "FOLLOW_UP_SCHEDULED" ||
    item.kind === "FOLLOW_UP_RESCHEDULED" ||
    item.kind === "FOLLOW_UP_COMPLETED" ||
    item.kind === "FOLLOW_UP_CANCELLED"
  ) {
    return "automation";
  }
  if (
    item.kind === "DRAFT_APPROVED" ||
    item.kind === "DRAFT_REJECTED" ||
    item.kind === "DRAFT_EDITED" ||
    item.kind === "LEAD_STATUS_CHANGED"
  ) {
    return "human";
  }
  if (
    item.is_draft ||
    item.kind === "QUALIFICATION_COMPLETED" ||
    item.kind.startsWith("SALES_RUN_")
  ) {
    return "ai";
  }
  return "system";
}

const lanePresentation: Record<
  TimelineLane,
  { label: string; className: string; icon: typeof Bot }
> = {
  customer: {
    label: "Customer",
    className: "border-l-info bg-info/5",
    icon: MessageSquareText,
  },
  ai: {
    label: "AI",
    className: "border-l-[var(--ai)] border-ai-border bg-ai/5",
    icon: Bot,
  },
  human: {
    label: "Human",
    className: "border-l-warning bg-warning/5",
    icon: UserRound,
  },
  outbound: {
    label: "Outbound",
    className: "border-l-success bg-success/5",
    icon: Mail,
  },
  automation: {
    label: "Automation",
    className: "border-l-primary bg-primary/5",
    icon: CalendarClock,
  },
  system: {
    label: "System",
    className: "border-l-border bg-card",
    icon: CheckCheck,
  },
};

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
      className="relative grid gap-3 p-4 sm:p-5"
      data-slot="conversation-timeline"
    >
      {items.map((item, index) => {
        const lane = laneFor(item);
        const laneMeta = lanePresentation[lane];
        const LaneIcon = laneMeta.icon;
        const failed =
          item.kind === "EMAIL_FAILED" ||
          item.kind === "FOLLOW_UP_EXECUTION_FAILED";
        const isDraft = item.is_draft;
        const isSent = item.is_sent_message;

        return (
          <li key={item.id} className="relative">
            {index < items.length - 1 ? (
              <span
                aria-hidden="true"
                className="bg-border absolute top-10 bottom-[-0.75rem] left-[1.15rem] w-px motion-safe:transition-opacity"
              />
            ) : null}
            <article
              className={cn(
                "border-border relative rounded-lg border border-l-4 p-4 shadow-none",
                laneMeta.className,
                failed && "border-l-destructive bg-destructive/5",
                isSent && "border-l-success",
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex min-h-6 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium",
                      lane === "ai"
                        ? "border-ai-border bg-ai/10 text-ai-text"
                        : "border-border bg-background text-muted-foreground",
                    )}
                  >
                    <LaneIcon className="size-3.5" aria-hidden="true" />
                    {laneMeta.label}
                  </span>
                  {isDraft ? <AiBadge label="Generated" /> : null}
                  {isSent ? (
                    <StatusBadge status="success" label="Sent to customer" />
                  ) : null}
                  {failed ? (
                    <StatusBadge status="failed" label="Failed" />
                  ) : null}
                  {item.kind === "SALES_RUN_WAITING_APPROVAL" ||
                  (isDraft &&
                    (item.kind === "DRAFT_GENERATED" ||
                      item.kind === "DRAFT_EDITED")) ? (
                    <StatusBadge status="warning" label="Needs your review" />
                  ) : null}
                </div>
                <RelativeTime value={item.occurred_at} />
              </div>

              <h4 className="mt-3 text-sm font-semibold tracking-tight">
                {kindLabels[item.kind] ?? item.title}
              </h4>

              {item.actor_type ? (
                <p className="text-muted-foreground mt-1 text-xs">
                  {actorLabels[item.actor_type]}
                  {item.summary ? ` · ${item.summary}` : null}
                </p>
              ) : item.summary ? (
                <p className="text-muted-foreground mt-1 text-xs leading-5">
                  {item.summary}
                </p>
              ) : null}

              {isDraft ? (
                <p className="text-ai-text mt-2 text-xs font-medium">
                  Prepared by FlowPilot AI · Not sent to the customer
                </p>
              ) : null}

              {item.body ? (
                <div
                  className={cn(
                    "mt-3 rounded-md border px-3 py-2.5 text-sm leading-6 whitespace-pre-wrap",
                    isDraft &&
                      "border-ai-border bg-ai/5 text-foreground italic",
                    isSent && "border-border bg-background",
                    failed && "border-destructive/20 bg-background",
                    !isDraft && !isSent && !failed && "border-border bg-background",
                  )}
                >
                  {item.body}
                </div>
              ) : null}

              {failed ? (
                <p className="text-muted-foreground mt-2 text-xs">
                  Email could not be delivered. Review details on the Lead
                  record if you need to retry.
                </p>
              ) : null}
            </article>
          </li>
        );
      })}
    </ol>
  );
}
