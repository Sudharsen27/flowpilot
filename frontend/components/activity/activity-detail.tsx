import { ArrowLeft, FileClock } from "lucide-react";
import type { ReactNode } from "react";

import { ActivityStatusBadge } from "@/components/activity/activity-status-badge";
import { ActivityTypeBadge } from "@/components/activity/activity-type-badge";
import type { ActivityEventItem } from "@/components/activity/activity-timeline";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

type ActivityDetailProps = {
  event?: ActivityEventItem;
  onBack?: () => void;
};

type DetailFieldProps = {
  label: string;
  value?: ReactNode;
};

function DetailField({ label, value }: DetailFieldProps) {
  return (
    <div className="grid gap-1.5">
      <dt className="text-muted-foreground text-xs font-medium">{label}</dt>
      <dd className="text-sm leading-6">{value ?? "No event selected."}</dd>
    </div>
  );
}

export function ActivityDetail({ event, onBack }: ActivityDetailProps) {
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
              className="text-base font-medium tracking-tight"
            >
              Event detail
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Inspect the source and context of a recorded event.
            </p>
          </div>
        </div>
        {event ? (
          <ActivityStatusBadge status={event.status} />
        ) : (
          <StatusBadge status="draft" label="Unavailable" />
        )}
      </header>

      {!event ? (
        <section
          className="border-border flex flex-col items-center justify-center border-b px-6 py-10 text-center"
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
            Event details will appear here after a real activity source exists
            and an event is selected.
          </p>
        </section>
      ) : null}

      <dl className="grid flex-1 content-start gap-6 p-5 sm:grid-cols-2 sm:p-6">
        <DetailField
          label="Event type"
          value={event ? <ActivityTypeBadge type={event.type} /> : undefined}
        />
        <DetailField label="Actor" value={event?.actor} />
        <DetailField label="Description" value={event?.description} />
        <DetailField label="Related object" value={event?.relatedObject} />
        <DetailField label="Timestamp" value={event?.timestamp} />
        <DetailField
          label="Status"
          value={
            event ? <ActivityStatusBadge status={event.status} /> : undefined
          }
        />
        <div className="sm:col-span-2">
          <DetailField label="Details and context" value={event?.details} />
        </div>
      </dl>
    </Card>
  );
}
