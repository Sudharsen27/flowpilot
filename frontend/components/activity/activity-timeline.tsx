import { History } from "lucide-react";

import {
  ActivityTypeBadge,
  type ActivityEventType,
} from "@/components/activity/activity-type-badge";
import {
  ActivityStatusBadge,
  type ActivityEventStatus,
} from "@/components/activity/activity-status-badge";
import { EmptyState } from "@/components/empty-state";
import { cn } from "@/lib/utils";

export type ActivityEventItem = {
  id: string;
  type: ActivityEventType;
  actor: string;
  description: string;
  relatedObject?: string;
  status: ActivityEventStatus;
  timestamp: string;
  details?: string;
};

type ActivityTimelineProps = {
  events: ActivityEventItem[];
  selectedId?: string;
  onSelect?: (event: ActivityEventItem) => void;
};

export function ActivityTimeline({
  events,
  selectedId,
  onSelect,
}: ActivityTimelineProps) {
  if (events.length === 0) {
    return (
      <EmptyState
        compact
        icon={<History />}
        className="max-w-none rounded-none border-x-0 border-b-0 shadow-none"
        title="No activity recorded"
        description="Activity will appear here when FlowPilot agents, workflows, integrations, approvals, and team members begin performing real work."
      />
    );
  }

  return (
    <ol
      aria-label="Activity timeline"
      className="divide-border divide-y"
      data-slot="activity-timeline"
    >
      {events.map((event) => {
        const isSelected = selectedId === event.id;
        return (
          <li key={event.id}>
            <button
              type="button"
              className={cn(
                "hover:bg-surface-subtle focus-visible:ring-ring/40 w-full p-4 text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-inset",
                isSelected && "bg-surface-subtle",
              )}
              aria-pressed={isSelected}
              onClick={() => onSelect?.(event)}
            >
              <span className="flex flex-wrap items-start justify-between gap-2">
                <ActivityTypeBadge type={event.type} />
                <span className="text-muted-foreground text-xs">
                  {event.timestamp}
                </span>
              </span>
              <span className="mt-3 block text-sm leading-6">
                {event.description}
              </span>
              <span className="text-muted-foreground mt-1 block text-xs">
                Actor: {event.actor}
              </span>
              <span className="mt-3 flex flex-wrap items-center gap-2">
                <ActivityStatusBadge status={event.status} />
                {event.relatedObject ? (
                  <span className="text-muted-foreground text-xs">
                    {event.relatedObject}
                  </span>
                ) : null}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
