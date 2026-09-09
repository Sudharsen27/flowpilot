import { KeyRound, Settings2, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const setupConcepts = [
  {
    title: "Permissions",
    description: "Define which approved operations a connection may use.",
    icon: ShieldCheck,
  },
  {
    title: "Data access",
    description: "Choose the business data available to FlowPilot.",
    icon: KeyRound,
  },
  {
    title: "Configuration requirements",
    description: "Review setup requirements before a connection is attempted.",
    icon: Settings2,
  },
] as const;

export function IntegrationSetupConcept() {
  return (
    <Card as="section" aria-labelledby="integration-setup-title">
      <CardContent className="grid gap-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3
              id="integration-setup-title"
              className="text-base font-medium tracking-tight"
            >
              Integration setup preview
            </h3>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              Setup details will appear here after an integration is supported
              and selected.
            </p>
          </div>
          <StatusBadge status="draft" label="No integration selected" />
        </div>

        <dl className="grid gap-4 sm:grid-cols-3">
          {setupConcepts.map((concept) => {
            const Icon = concept.icon;
            return (
              <div
                key={concept.title}
                className="border-border bg-surface-subtle rounded-lg border p-4"
              >
                <dt className="flex items-center gap-2 text-sm font-medium">
                  <Icon
                    className="text-muted-foreground size-4"
                    aria-hidden="true"
                  />
                  {concept.title}
                </dt>
                <dd className="text-muted-foreground mt-2 text-xs leading-5">
                  {concept.description}
                </dd>
                <dd className="mt-3 text-xs font-medium">Not available</dd>
              </div>
            );
          })}
        </dl>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-muted-foreground text-xs">
            No credentials are requested or stored by this UI.
          </p>
          <Button type="button" disabled>
            Configure connection
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
