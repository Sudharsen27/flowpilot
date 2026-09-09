import { ListChecks, Zap } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const triggerConcepts = [
  "New customer enquiry",
  "New lead",
  "Incoming message",
  "Form submission",
  "Scheduled event",
  "External webhook",
] as const;

const actionConcepts = [
  "Qualify lead",
  "Send response",
  "Create CRM record",
  "Schedule follow-up",
  "Request human approval",
  "Update record",
  "Notify team",
] as const;

type ConceptListProps = {
  items: readonly string[];
  label: string;
  stateLabel: string;
};

function ConceptList({ items, label, stateLabel }: ConceptListProps) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2" aria-label={label}>
      {items.map((item) => (
        <li
          key={item}
          className="border-border bg-surface-subtle flex min-h-10 items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm"
        >
          {item}
          <span className="text-muted-foreground shrink-0 text-xs">
            {stateLabel}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function WorkflowConcepts() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card as="section" aria-labelledby="trigger-concepts-title">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3
                id="trigger-concepts-title"
                className="text-card-title font-medium tracking-tight"
              >
                Trigger concepts
              </h3>
              <CardDescription className="mt-1.5">
                Events that may eventually start a configured workflow.
              </CardDescription>
            </div>
            <div
              className="bg-muted text-muted-foreground flex size-8 shrink-0 items-center justify-center rounded-md"
              aria-hidden="true"
            >
              <Zap className="size-4" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4">
          <StatusBadge status="draft" label="None connected" />
          <ConceptList
            items={triggerConcepts}
            label="Available trigger concepts"
            stateLabel="Concept"
          />
        </CardContent>
      </Card>

      <Card as="section" aria-labelledby="action-concepts-title">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3
                id="action-concepts-title"
                className="text-card-title font-medium tracking-tight"
              >
                Action concepts
              </h3>
              <CardDescription className="mt-1.5">
                Operations a workflow may eventually request or coordinate.
              </CardDescription>
            </div>
            <div
              className="bg-muted text-muted-foreground flex size-8 shrink-0 items-center justify-center rounded-md"
              aria-hidden="true"
            >
              <ListChecks className="size-4" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4">
          <StatusBadge status="draft" label="Execution unavailable" />
          <ConceptList
            items={actionConcepts}
            label="Available action concepts"
            stateLabel="Concept"
          />
        </CardContent>
      </Card>
    </div>
  );
}
