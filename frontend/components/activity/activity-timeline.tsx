import { History } from "lucide-react";

import { ActivityTypeBadge } from "@/components/activity/activity-type-badge";
import { formatTimestamp } from "@/components/agents/execution-status";
import { AiBadge } from "@/components/ai/ai-badge";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";
import { statusPresentation } from "@/lib/status";
import type { ActivityActorType, ActivityEvent } from "@/types/api";

export const actorLabels: Record<ActivityActorType, string> = {
  USER: "Team member",
  AGENT: "Sales Agent",
  SYSTEM: "System",
  PUBLIC_VISITOR: "Website visitor",
};

export const entityLabels: Record<ActivityEvent["entity_type"], string> = {
  LEAD: "Lead",
  SALES_RUN: "Sales Run",
  LEAD_EMAIL_SEND: "Email",
  AGENT_EXECUTION: "Agent execution",
  LEAD_FOLLOW_UP: "Follow-up",
  LEAD_FOLLOW_UP_EXECUTION: "Follow-up execution",
  LEAD_RESPONSE_DRAFT: "Response draft",
  LEAD_QUALIFICATION: "Qualification",
};

type ActivityTimelineProps = {
  events: ActivityEvent[];
  selectedId?: string;
  onSelect?: (event: ActivityEvent) => void;
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
        title="No activity yet"
        description="Activity appears here when your organization captures enquiries, runs the Sales Agent, reviews drafts, sends email, or completes follow-ups."
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
        const status = event.status
          ? statusPresentation(event.status, event.status)
          : null;
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
                <span className="flex flex-wrap items-center gap-2">
                  <ActivityTypeBadge type={event.type} />
                  {event.type === "AI_ACTION" ? (
                    <AiBadge label="Agent" />
                  ) : null}
                </span>
                <span className="text-muted-foreground text-xs">
                  {formatTimestamp(event.occurred_at) ?? "—"}
                </span>
              </span>
              <span className="mt-3 block text-sm font-medium leading-6">
                {event.title}
              </span>
              <span className="text-muted-foreground mt-1 block text-xs">
                {actorLabels[event.actor_type]}
              </span>
              <span className="mt-3 flex flex-wrap items-center gap-2">
                {status ? (
                  <StatusBadge status={status.status} label={status.label} />
                ) : null}
                <span className="text-muted-foreground text-xs">
                  {entityLabels[event.entity_type]}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
