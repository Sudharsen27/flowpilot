import { ShieldCheck } from "lucide-react";

import {
  ActivityTypeBadge,
  type ActivityEventType,
} from "@/components/activity/activity-type-badge";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const eventConcepts: Array<{
  type: ActivityEventType;
  description: string;
}> = [
  {
    type: "ai-action",
    description: "Actions proposed or performed by an AI agent.",
  },
  {
    type: "workflow",
    description: "Important workflow lifecycle and execution events.",
  },
  {
    type: "approval",
    description: "Human review and approval decision events.",
  },
  {
    type: "integration",
    description: "Connection and business-system events.",
  },
  {
    type: "human-action",
    description: "Important actions initiated by a team member.",
  },
  {
    type: "system-event",
    description: "Platform-level operational events.",
  },
];

const auditQuestions = [
  "What happened",
  "When it happened",
  "Which agent or person initiated it",
  "Which system or workflow was involved",
] as const;

export function ActivityConcepts() {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
      <Card as="section" aria-labelledby="event-categories-title">
        <CardContent className="grid gap-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3
                id="event-categories-title"
                className="text-base font-medium tracking-tight"
              >
                Event categories
              </h3>
              <p className="text-muted-foreground mt-1 text-sm leading-6">
                UI concepts for classifying future activity records.
              </p>
            </div>
            <StatusBadge status="draft" label="Concepts only" />
          </div>
          <ul
            className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
            aria-label="Activity event type concepts"
          >
            {eventConcepts.map((event) => (
              <li
                key={event.type}
                className="border-border bg-surface-subtle rounded-lg border p-3"
              >
                <ActivityTypeBadge type={event.type} />
                <p className="text-muted-foreground mt-2 text-xs leading-5">
                  {event.description}
                </p>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card as="section" variant="subtle" aria-labelledby="audit-context-title">
        <CardContent>
          <div
            className="bg-card text-success-text border-border flex size-9 items-center justify-center rounded-lg border"
            aria-hidden="true"
          >
            <ShieldCheck className="size-4" />
          </div>
          <h3
            id="audit-context-title"
            className="mt-4 text-base font-medium tracking-tight"
          >
            Understand important activity
          </h3>
          <p className="text-muted-foreground mt-2 text-sm leading-6">
            A future activity record can help teams review:
          </p>
          <ul className="mt-3 grid gap-2">
            {auditQuestions.map((question) => (
              <li key={question} className="flex items-start gap-2 text-xs">
                <span
                  className="bg-muted-foreground mt-1.5 size-1 shrink-0 rounded-full"
                  aria-hidden="true"
                />
                {question}
              </li>
            ))}
          </ul>
          <p className="text-muted-foreground mt-4 text-xs leading-5">
            No audit-log persistence, event ingestion, or compliance guarantee
            is provided by this UI.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
