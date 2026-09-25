"use client";

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
import Link from "next/link";
import { useRef, useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const workflowSteps = [
  {
    title: "Trigger",
    description: "A business event starts the workflow.",
    detail:
      "Triggers describe the business events that a future configured workflow may respond to.",
    icon: CircleDot,
    related: [
      { href: "/leads", label: "Review Leads" },
      { href: "/integrations", label: "Explore Integrations" },
    ],
  },
  {
    title: "AI agent / action",
    description: "Configured work is prepared.",
    detail:
      "An AI agent or action may eventually prepare work within the boundaries configured for the workflow.",
    icon: Bot,
    related: [{ href: "/agents", label: "Review AI Agents" }],
  },
  {
    title: "Condition",
    description: "Rules determine the next path.",
    detail:
      "Conditions represent planned rules that may determine which workflow path is appropriate.",
    icon: GitBranch,
    related: [],
  },
  {
    title: "Approval",
    description: "A person reviews work when required.",
    detail:
      "Approval represents a planned human-control point before a sensitive workflow action.",
    icon: ShieldCheck,
    related: [{ href: "/approvals", label: "Open Approvals" }],
  },
  {
    title: "Action",
    description: "An approved operation can run.",
    detail:
      "Actions represent operations a future workflow may coordinate after its conditions and approvals are satisfied.",
    icon: Play,
    related: [
      { href: "/leads", label: "Review Leads" },
      { href: "/integrations", label: "Explore Integrations" },
    ],
  },
  {
    title: "Outcome",
    description: "The result is recorded and surfaced.",
    detail:
      "Outcomes describe how future workflow results may be recorded and surfaced to the team.",
    icon: Flag,
    related: [{ href: "/activity", label: "View Activity" }],
  },
] as const;

type WorkflowStepTitle = (typeof workflowSteps)[number]["title"];

export function WorkflowBlueprint() {
  const [selectedStep, setSelectedStep] = useState<WorkflowStepTitle>(
    workflowSteps[0].title,
  );
  const detailRef = useRef<HTMLElement>(null);
  const selected = workflowSteps.find((step) => step.title === selectedStep) ?? workflowSteps[0];

  function selectStep(title: WorkflowStepTitle) {
    setSelectedStep(title);
    requestAnimationFrame(() => detailRef.current?.focus());
  }

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
              <li key={step.title} className="relative">
                <button
                  type="button"
                  aria-pressed={selectedStep === step.title}
                  aria-controls="workflow-step-detail"
                  onClick={() => selectStep(step.title)}
                  className={`border-border bg-surface-subtle hover:bg-muted/60 focus-visible:ring-ring w-full rounded-lg border p-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-inset ${selectedStep === step.title ? "border-primary bg-primary/5" : ""}`}
                >
                  <span
                    className="bg-card text-muted-foreground border-border flex size-8 items-center justify-center rounded-md border"
                    aria-hidden="true"
                  >
                    <Icon className="size-4" />
                  </span>
                  <span className="mt-3 block text-sm font-medium">
                    {step.title}
                  </span>
                  <span className="text-muted-foreground mt-1 block text-xs leading-5">
                    {step.description}
                  </span>
                </button>
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

        <section
          id="workflow-step-detail"
          ref={detailRef}
          tabIndex={-1}
          aria-labelledby="workflow-step-detail-title"
          className="border-border bg-surface-subtle grid gap-3 rounded-lg border p-4 outline-none focus-visible:ring-ring focus-visible:ring-2"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-muted-foreground text-xs font-medium uppercase">
                Selected blueprint step
              </p>
              <h4 id="workflow-step-detail-title" className="mt-1 text-sm font-semibold">
                {selected.title}
              </h4>
            </div>
            <StatusBadge status="draft" label="Planned concept" />
          </div>
          <p className="text-muted-foreground max-w-3xl text-sm leading-6">
            {selected.detail}
          </p>
          {selected.related.length > 0 ? (
            <nav aria-label={`${selected.title} related workspaces`}>
              <ul className="flex flex-wrap gap-2">
                {selected.related.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="border-border bg-background hover:bg-muted focus-visible:ring-ring inline-flex min-h-8 items-center rounded-lg border px-2.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ) : null}
        </section>

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
