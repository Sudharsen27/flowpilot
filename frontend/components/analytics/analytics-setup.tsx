import { BarChart3, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Card, CardContent } from "@/components/ui/card";

const dataSources = [
  { href: "/leads", label: "Leads" },
  { href: "/inbox", label: "Conversations" },
  { href: "/agents", label: "Agents" },
  { href: "/workflows", label: "Workflows" },
  { href: "/approvals", label: "Approvals" },
  { href: "/integrations", label: "Integrations" },
] as const;

export function AnalyticsSetup() {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
      <EmptyState
        icon={<BarChart3 />}
        className="max-w-none"
        title="Analytics will become available as FlowPilot starts processing real business activity"
        description="Measurements will eventually come from leads, conversations, agents, workflows, approvals, and integrations. None of those systems are producing analytics yet."
        action={
          <nav aria-label="Explore related workspaces">
            <ul className="flex flex-wrap gap-2">
              {dataSources.map((source) => (
                <li key={source.href}>
                  <Link
                    href={source.href}
                    className="border-border bg-background hover:bg-muted focus-visible:ring-ring inline-flex min-h-8 items-center rounded-lg border px-2.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                  >
                    {source.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        }
      />

      <Card
        as="section"
        variant="subtle"
        aria-labelledby="analytics-trust-title"
      >
        <CardContent>
          <div
            className="bg-card text-success-text border-border flex size-9 items-center justify-center rounded-lg border"
            aria-hidden="true"
          >
            <ShieldCheck className="size-4" />
          </div>
          <h3
            id="analytics-trust-title"
            className="mt-4 text-base font-medium tracking-tight"
          >
            Transparent visibility
          </h3>
          <p className="text-muted-foreground mt-2 text-sm leading-6">
            Analytics will eventually help teams see what FlowPilot is doing and
            the business outcomes it produces from recorded activity.
          </p>
          <p className="text-muted-foreground mt-3 text-xs leading-5">
            This screen does not calculate performance, accuracy, attribution,
            or compliance metrics.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
