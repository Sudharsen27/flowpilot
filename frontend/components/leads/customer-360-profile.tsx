import Link from "next/link";
import { Inbox, Mail, Phone, UserRound } from "lucide-react";

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
  loading?: boolean;
};

export function Customer360Profile({
  lead,
  conversationState = null,
  loading = false,
}: Customer360ProfileProps) {
  if (loading) {
    return (
      <section
        className="bg-card border-border rounded-lg border p-4 sm:p-5"
        aria-labelledby="customer-360-profile-title"
      >
        <h2 id="customer-360-profile-title" className="sr-only">
          Customer profile
        </h2>
        <div className="grid gap-3" role="status">
          <Skeleton className="h-7 w-44" />
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <span className="sr-only">Loading customer profile</span>
        </div>
      </section>
    );
  }

  const company = lead.company?.trim() || null;
  const email = lead.email?.trim() || null;
  const phone = lead.phone?.trim() || null;

  return (
    <section
      className="bg-card border-border grid content-start gap-5 rounded-lg border p-4 sm:p-5"
      aria-labelledby="customer-360-profile-title"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        <span
          className="bg-muted text-muted-foreground mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-lg"
          aria-hidden="true"
        >
          <UserRound className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-muted-foreground text-[0.6875rem] font-medium tracking-wide uppercase">
            Customer
          </p>
          <h2
            id="customer-360-profile-title"
            className="mt-1 text-lg font-semibold tracking-tight text-balance sm:text-xl"
          >
            {lead.name}
          </h2>
          <p className="text-muted-foreground mt-1 truncate text-sm">
            {company ?? "No company on file"}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <LeadStatusBadge status={lead.status} />
            {conversationState ? (
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
            ) : null}
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-muted-foreground text-[0.6875rem] font-medium tracking-wide uppercase">
          Contact
        </h3>
        <dl className="mt-2.5 grid gap-2.5">
          <DetailRow
            label="Email"
            icon={<Mail />}
            value={
              email ? (
                <a
                  href={`mailto:${email}`}
                  className="hover:text-foreground underline-offset-4 hover:underline"
                >
                  {email}
                </a>
              ) : (
                "—"
              )
            }
            muted={!email}
          />
          <DetailRow
            label="Phone"
            icon={<Phone />}
            value={
              phone ? (
                <a
                  href={`tel:${phone}`}
                  className="hover:text-foreground underline-offset-4 hover:underline"
                >
                  {phone}
                </a>
              ) : (
                "—"
              )
            }
            muted={!phone}
          />
          <DetailRow label="Source" value={inboxSourceLabels[lead.source]} />
          <DetailRow
            label="Updated"
            value={<RelativeTime value={lead.updated_at} className="text-sm" />}
          />
          <DetailRow
            label="Created"
            value={<RelativeTime value={lead.created_at} className="text-sm" />}
          />
        </dl>
      </div>

      <div className="border-border border-t pt-5">
        <h3 className="text-sm font-medium">What they want</h3>
        <p className="text-muted-foreground mt-1 text-xs">
          Original customer enquiry — not rewritten by AI.
        </p>
        {lead.enquiry?.trim() ? (
          <p className="text-foreground mt-3 text-sm leading-6 whitespace-pre-wrap">
            {lead.enquiry}
          </p>
        ) : (
          <p className="text-muted-foreground mt-3 text-sm italic">
            No enquiry recorded for this lead yet.
          </p>
        )}
      </div>

      {lead.notes?.trim() ? (
        <div className="border-border border-t pt-5">
          <h3 className="text-sm font-medium">Internal notes</h3>
          <p className="text-muted-foreground mt-3 text-sm leading-6 whitespace-pre-wrap">
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
