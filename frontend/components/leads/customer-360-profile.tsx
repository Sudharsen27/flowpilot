import Link from "next/link";
import { Inbox, UserRound } from "lucide-react";

import { DetailRow } from "@/components/data-display/detail-row";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { RelativeTime } from "@/components/ui/relative-time";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { inboxSourceLabels, inboxStateLabels } from "@/lib/inbox-labels";
import type { InboxConversationState, Lead } from "@/types/api";

type Customer360ProfileProps = {
  lead: Lead;
  conversationState?: InboxConversationState | null;
  needsApproval?: boolean;
  loading?: boolean;
};

export function Customer360Profile({
  lead,
  conversationState = null,
  needsApproval = false,
  loading = false,
}: Customer360ProfileProps) {
  if (loading) {
    return (
      <section
        className="bg-card border-border rounded-lg border p-4"
        aria-labelledby="customer-360-profile-title"
      >
        <h2 id="customer-360-profile-title" className="sr-only">
          Customer profile
        </h2>
        <div className="grid gap-3" role="status">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <span className="sr-only">Loading customer profile</span>
        </div>
      </section>
    );
  }

  return (
    <section
      className="bg-card border-border grid content-start gap-4 rounded-lg border p-4"
      aria-labelledby="customer-360-profile-title"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className="bg-muted text-muted-foreground flex size-9 shrink-0 items-center justify-center rounded-lg"
            aria-hidden="true"
          >
            <UserRound className="size-4" />
          </span>
          <div className="min-w-0">
            <h2
              id="customer-360-profile-title"
              className="truncate text-base font-semibold tracking-tight"
            >
              {lead.name}
            </h2>
            <p className="text-muted-foreground mt-0.5 truncate text-sm">
              {lead.company?.trim() || "No company on file"}
            </p>
          </div>
        </div>
        <LeadStatusBadge status={lead.status} />
      </div>

      {needsApproval ? (
        <div
          className="border-warning/30 bg-warning/10 rounded-md border px-3 py-2.5"
          role="status"
        >
          <p className="text-warning-text text-sm font-medium">
            Needs your review
          </p>
          <p className="text-muted-foreground mt-1 text-xs leading-5">
            An AI draft or Sales Run is waiting. Approve and send from this
            workspace — not from Inbox.
          </p>
        </div>
      ) : null}

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
        <DetailRow label="Source" value={inboxSourceLabels[lead.source]} />
        {conversationState ? (
          <DetailRow
            label="Conversation"
            value={
              <StatusBadge
                status={
                  conversationState === "NEEDS_APPROVAL"
                    ? "warning"
                    : conversationState === "CLOSED"
                      ? "success"
                      : "active"
                }
                label={inboxStateLabels[conversationState]}
              />
            }
          />
        ) : null}
        <DetailRow
          label="Updated"
          value={<RelativeTime value={lead.updated_at} className="text-sm" />}
        />
        <DetailRow
          label="Created"
          value={<RelativeTime value={lead.created_at} className="text-sm" />}
        />
      </dl>

      <div className="border-border border-t pt-4">
        <h3 className="text-sm font-medium">What they want</h3>
        {lead.enquiry?.trim() ? (
          <p className="text-muted-foreground mt-2 text-sm leading-6 whitespace-pre-wrap">
            {lead.enquiry}
          </p>
        ) : (
          <p className="text-muted-foreground mt-2 text-sm italic">
            No enquiry recorded for this lead yet.
          </p>
        )}
      </div>

      {lead.notes?.trim() ? (
        <div className="border-border border-t pt-4">
          <h3 className="text-sm font-medium">Internal notes</h3>
          <p className="text-muted-foreground mt-2 text-sm leading-6 whitespace-pre-wrap">
            {lead.notes}
          </p>
        </div>
      ) : null}

      <div className="border-border flex flex-wrap gap-3 border-t pt-4">
        <Link
          href={`/inbox?lead=${encodeURIComponent(lead.id)}`}
          className="text-foreground inline-flex items-center gap-1.5 text-sm font-medium underline-offset-4 hover:underline"
        >
          <Inbox className="size-3.5" aria-hidden="true" />
          Open in Inbox
        </Link>
      </div>
    </section>
  );
}
