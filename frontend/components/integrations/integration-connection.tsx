import {
  ArrowDown,
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  Plug,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const connectionSteps = [
  { label: "Business tools", icon: BriefcaseBusiness },
  { label: "Integrations", icon: Plug },
  { label: "FlowPilot agents", icon: Bot },
  { label: "Workflows / actions", icon: Workflow },
] as const;

export function IntegrationConnection() {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
      <Card as="section" aria-labelledby="integration-connection-title">
        <CardContent className="grid gap-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3
                id="integration-connection-title"
                className="text-base font-medium tracking-tight"
              >
                Integrations across FlowPilot
              </h3>
              <p className="text-muted-foreground mt-1 text-sm leading-6">
                A conceptual path for how approved business tools may eventually
                connect with agents and workflows.
              </p>
            </div>
            <StatusBadge status="draft" label="Concept only" />
          </div>

          <ol
            className="grid gap-6 md:grid-cols-4"
            aria-label="Conceptual integration connection"
          >
            {connectionSteps.map((step, index) => {
              const Icon = step.icon;
              const isLast = index === connectionSteps.length - 1;
              return (
                <li
                  key={step.label}
                  className="border-border bg-surface-subtle relative flex min-h-24 flex-col items-center justify-center rounded-lg border p-4 text-center"
                >
                  <Icon
                    className="text-muted-foreground size-5"
                    aria-hidden="true"
                  />
                  <span className="mt-2 text-sm font-medium">{step.label}</span>
                  {!isLast ? (
                    <>
                      <ArrowDown
                        className="text-muted-foreground absolute top-full left-1/2 mt-1 size-4 -translate-x-1/2 md:hidden"
                        aria-hidden="true"
                      />
                      <ArrowRight
                        className="text-muted-foreground absolute top-1/2 left-full ml-1 size-4 -translate-y-1/2 max-md:hidden"
                        aria-hidden="true"
                      />
                    </>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </CardContent>
      </Card>

      <Card
        as="section"
        variant="subtle"
        aria-labelledby="integration-trust-title"
      >
        <CardContent>
          <div
            className="bg-card text-success-text border-border flex size-9 items-center justify-center rounded-lg border"
            aria-hidden="true"
          >
            <ShieldCheck className="size-4" />
          </div>
          <h3
            id="integration-trust-title"
            className="mt-4 text-base font-medium tracking-tight"
          >
            Permissions and control
          </h3>
          <p className="text-muted-foreground mt-2 text-sm leading-6">
            Future integration design should use explicit permissions and
            organization-level controls so businesses can decide which systems
            and operations FlowPilot may access.
          </p>
          <p className="text-muted-foreground mt-3 text-xs leading-5">
            No connection, credential, token, or permission enforcement is
            implemented in this screen.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
