import { BarChart3, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Card, CardContent } from "@/components/ui/card";

const dataSources = [
  { href: "/leads", label: "View Leads", primary: true },
  { href: "/inbox", label: "AI Inbox", primary: false },
  { href: "/agents", label: "Agents", primary: false },
  { href: "/workflows", label: "Workflows", primary: false },
  { href: "/approvals", label: "Approvals", primary: false },
  { href: "/integrations", label: "Integrations", primary: false },
] as const;

export function AnalyticsSetup() {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
      <EmptyState
        icon={<BarChart3 />}
        className="max-w-none"
        title="Analytics is coming soon"
        description="Reporting metrics and performance insights will appear here once analytics data is available."
        action={
          <nav aria-label="Explore related workspaces">
            <ul className="flex flex-wrap gap-2">
              {dataSources.map((source) => (
                <li key={source.href}>
                  <Link
                    href={source.href}
                    className={
                      source.primary
                        ? "focus-visible:ring-ring bg-primary text-primary-foreground hover:bg-primary/80 inline-flex min-h-8 items-center rounded-lg px-2.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                        : "border-border bg-background hover:bg-muted focus-visible:ring-ring inline-flex min-h-8 items-center rounded-lg border px-2.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                    }
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
            Analytics will help teams understand recorded FlowPilot activity and
            the business outcomes it produces when reporting is available.
          </p>
          <p className="text-muted-foreground mt-3 text-xs leading-5">
            This screen does not calculate performance, accuracy, attribution,
            or compliance metrics yet.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
