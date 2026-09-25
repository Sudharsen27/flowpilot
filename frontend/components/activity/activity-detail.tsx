import { ArrowLeft, FileClock } from "lucide-react";
import Link from "next/link";
import type { ReactNode, RefObject } from "react";

import {
  actorLabels,
  entityLabels,
} from "@/components/activity/activity-timeline";
import { humanizeActivityStatus } from "@/components/activity/activity-status-badge";
import { ActivityTypeBadge } from "@/components/activity/activity-type-badge";
import { AiBadge } from "@/components/ai/ai-badge";
import { DetailRow } from "@/components/data-display/detail-row";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { RelativeTime } from "@/components/ui/relative-time";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";
import { statusPresentation } from "@/lib/status";
import type { ActivityEvent } from "@/types/api";

type ActivityDetailProps = {
  event?: ActivityEvent | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onBack?: () => void;
  headingRef?: RefObject<HTMLHeadingElement | null>;
};

function DetailField({
  label,
  value,
}: {
  label: string;
  value?: ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <dt className="text-muted-foreground text-xs font-medium">{label}</dt>
      <dd className="text-sm leading-6">{value ?? "—"}</dd>
    </div>
  );
}

export function ActivityDetail({
  event,
  loading = false,
  error = null,
  onRetry,
  onBack,
  headingRef,
}: ActivityDetailProps) {
  const status = event?.status
    ? statusPresentation(event.status, humanizeActivityStatus(event.status))
    : null;

  return (
    <Card
      as="section"
      className="flex min-h-[40rem] min-w-0 flex-col overflow-hidden"
      aria-labelledby="activity-detail-title"
    >
      <header className="border-border flex flex-wrap items-start justify-between gap-3 border-b px-4 py-4 sm:px-5">
        <div className="flex min-w-0 items-start gap-2">
          {onBack ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="Back to activity timeline"
              onClick={onBack}
            >
              <ArrowLeft aria-hidden="true" />
            </Button>
          ) : null}
          <div className="min-w-0">
            <h3
              id="activity-detail-title"
              tabIndex={-1}
              ref={headingRef}
              className="text-base font-medium tracking-tight"
            >
              Event detail
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Inspect a recorded organization event.
            </p>
          </div>
        </div>
        {event && status ? (
          <StatusBadge status={status.status} label={status.label} />
        ) : null}
      </header>

      {!event ? (
        loading ? (
          <div className="grid gap-3 p-5" role="status">
            <Skeleton className="h-8 w-40" />
            <Skeleton className="h-24" />
            <span className="sr-only">Loading event detail</span>
          </div>
        ) : (
        <section
          className="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center"
          aria-labelledby="event-selection-title"
        >
          <div
            className="bg-muted text-muted-foreground flex size-10 items-center justify-center rounded-lg"
            aria-hidden="true"
          >
            <FileClock className="size-5" />
          </div>
          <h4 id="event-selection-title" className="mt-4 text-sm font-medium">
            No event selected
          </h4>
          <p className="text-muted-foreground mt-1.5 max-w-sm text-sm leading-6">
            Select an event from the timeline to see when it happened and which
            record it relates to.
          </p>
        </section>
        )
      ) : loading && !event.summary ? (
        <div className="grid gap-3 p-5" role="status">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-24" />
          <span className="sr-only">Loading event detail</span>
        </div>
      ) : (
        <div className="grid flex-1 content-start gap-6 p-5 sm:p-6">
          {error ? (
            <div
              className="border-destructive/25 bg-destructive/5 grid gap-3 rounded-lg border p-4"
              role="alert"
            >
              <div>
                <p className="text-danger-text text-sm font-medium">
                  Event details could not be loaded
                </p>
                <p className="text-muted-foreground mt-1 text-sm leading-5">
                  {error}
                </p>
              </div>
              {onRetry ? (
                <Button type="button" variant="outline" onClick={onRetry}>
                  Retry detail
                </Button>
              ) : null}
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <ActivityTypeBadge type={event.type} />
            {event.type === "AI_ACTION" ? <AiBadge label="Agent" /> : null}
          </div>
          <h4 className="text-card-title font-medium tracking-tight">
            {event.title}
          </h4>
          <dl className="grid gap-5 sm:grid-cols-2">
            <DetailField
              label="When"
              value={<RelativeTime value={event.occurred_at} />}
            />
            <DetailField label="Actor" value={actorLabels[event.actor_type]} />
            <DetailField
              label="Entity"
              value={entityLabels[event.entity_type]}
            />
            <DetailField label="Entity ID" value={event.entity_id} />
            <div className="sm:col-span-2">
              <DetailRow label="Summary" value={event.summary ?? "—"} />
            </div>
          </dl>
          <div className="flex flex-wrap gap-2">
            {event.lead_id ? (
              <Link
                href={`/leads/${event.lead_id}`}
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                Open lead
              </Link>
            ) : null}
            {event.agent_id ? (
              <Link
                href={`/agents/${event.agent_id}`}
                className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
              >
                Open agent
              </Link>
            ) : null}
          </div>
        </div>
      )}
    </Card>
  );
}
