import {
  ArrowDown,
  ArrowRight,
  Bot,
  CircleDot,
  Flag,
  GitBranch,
  Play,
  ShieldCheck,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const workflowSteps = [
  {
    title: "Trigger",
    description: "A business event starts the workflow.",
    icon: CircleDot,
  },
  {
    title: "AI agent / action",
    description: "Configured work is prepared.",
    icon: Bot,
  },
  {
    title: "Condition",
    description: "Rules determine the next path.",
    icon: GitBranch,
  },
  {
    title: "Approval",
    description: "A person reviews work when required.",
    icon: ShieldCheck,
  },
  {
    title: "Action",
    description: "An approved operation can run.",
    icon: Play,
  },
  {
    title: "Outcome",
    description: "The result is recorded and surfaced.",
    icon: Flag,
  },
] as const;

export function WorkflowBlueprint() {
  return (
    <Card as="section" aria-labelledby="workflow-blueprint-title">
      <CardContent className="grid gap-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3
              id="workflow-blueprint-title"
              className="text-base font-medium tracking-tight"
            >
              Workflow structure
            </h3>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              A non-functional model of how future workflow configuration may
              connect business logic.
            </p>
          </div>
          <StatusBadge status="draft" label="Blueprint only" />
        </div>

        <ol
          className="grid gap-6 lg:grid-cols-6"
          aria-label="Conceptual workflow steps"
        >
          {workflowSteps.map((step, index) => {
            const Icon = step.icon;
            const isLast = index === workflowSteps.length - 1;
            return (
              <li
                key={step.title}
                className="border-border bg-surface-subtle relative rounded-lg border p-4"
              >
                <div
                  className="bg-card text-muted-foreground border-border flex size-8 items-center justify-center rounded-md border"
                  aria-hidden="true"
                >
                  <Icon className="size-4" />
                </div>
                <h4 className="mt-3 text-sm font-medium">{step.title}</h4>
                <p className="text-muted-foreground mt-1 text-xs leading-5">
                  {step.description}
                </p>
                {!isLast ? (
                  <>
                    <ArrowDown
                      className="text-muted-foreground absolute top-full left-1/2 mt-1 size-4 -translate-x-1/2 lg:hidden"
                      aria-hidden="true"
                    />
                    <ArrowRight
                      className="text-muted-foreground absolute top-1/2 left-full ml-1 size-4 -translate-y-1/2 max-lg:hidden"
                      aria-hidden="true"
                    />
                  </>
                ) : null}
              </li>
            );
          })}
        </ol>

        <div className="border-border bg-surface-subtle rounded-lg border p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium">Planned agent connection</p>
            <StatusBadge status="draft" label="Configuration concept" />
          </div>
          <p className="text-muted-foreground mt-2 text-xs leading-5">
            A workflow may eventually connect a trigger to an AI agent,
            qualification, human approval, and follow-up.
          </p>
          <div
            className="mt-3 flex flex-wrap items-center gap-2 text-xs font-medium"
            aria-label="Planned agent workflow example"
          >
            {[
              "Trigger",
              "AI agent",
              "Qualification",
              "Approval",
              "Follow-up",
            ].map((step, index) => (
              <span key={step} className="inline-flex items-center gap-2">
                {index > 0 ? (
                  <ArrowRight
                    className="text-muted-foreground size-3.5"
                    aria-hidden="true"
                  />
                ) : null}
                <span className="bg-card border-border rounded-md border px-2 py-1">
                  {step}
                </span>
              </span>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
