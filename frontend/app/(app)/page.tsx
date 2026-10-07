"use client";

import { Bot, CheckCheck, Users } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AiWorkforceStatus } from "@/components/command-center/ai-workforce-status";
import { BusinessOverview } from "@/components/command-center/business-overview";
import { NeedsAttention } from "@/components/command-center/needs-attention";
import { QuickActions } from "@/components/command-center/quick-actions";
import { RecentActivity } from "@/components/command-center/recent-activity";
import { WorkspaceCommand } from "@/components/command-center/workspace-command";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAgents } from "@/lib/api/agents";
import { getLeads } from "@/lib/api/leads";
import { listOrganizationSalesRuns } from "@/lib/api/sales-runs";
import type { Agent } from "@/types/api";

type DashboardData = {
  agents: Agent[];
  leadTotal: number;
  newLeads: number;
  waitingApproval: number;
};

function CommandCenterNextStep({ data }: { data: DashboardData }) {
  if (data.waitingApproval > 0) {
    return (
      <Card as="section" variant="information" aria-labelledby="next-step-heading">
        <CardHeader>
          <CardTitle id="next-step-heading">Your next step</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium">Review the response waiting for approval.</p>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              Approval is required before a response can be sent.
            </p>
          </div>
          <Link href="/approvals" className={buttonVariants({ variant: "default" })}>
            Review Approvals
            <CheckCheck aria-hidden="true" />
          </Link>
        </CardContent>
      </Card>
    );
  }

  if (data.leadTotal === 0) {
    return (
      <Card as="section" variant="information" aria-labelledby="next-step-heading">
        <CardHeader>
          <CardTitle id="next-step-heading">Start with a lead</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium">Create your first lead to begin the sales flow.</p>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              You can create one here or optionally enable website enquiries in Settings. An AI Agent can qualify a lead and draft a response; a person reviews and approves it before sending.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/leads" className={buttonVariants({ variant: "default" })}>
              Open Leads
              <Users aria-hidden="true" />
            </Link>
            <Link href="/settings" className={buttonVariants({ variant: "outline" })}>
              Website enquiries (optional)
            </Link>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (data.agents.length === 0) {
    return (
      <Card as="section" variant="information" aria-labelledby="next-step-heading">
        <CardHeader>
          <CardTitle id="next-step-heading">Configure an AI Agent</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium">Your leads are ready for an agent.</p>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              Configure an agent before asking FlowPilot to qualify leads or draft responses.
            </p>
          </div>
          <Link href="/agents" className={buttonVariants({ variant: "default" })}>
            Open AI Agents
            <Bot aria-hidden="true" />
          </Link>
        </CardContent>
      </Card>
    );
  }

  if (data.newLeads > 0) {
    return (
      <Card as="section" variant="information" aria-labelledby="next-step-heading">
        <CardHeader>
          <CardTitle id="next-step-heading">Qualify a new lead</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium">There are {data.newLeads} leads with New status.</p>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              Review a lead in Leads to run qualification and, when useful, generate a response draft for human approval.
            </p>
          </div>
          <Link href="/leads" className={buttonVariants({ variant: "default" })}>
            Open Leads
            <Users aria-hidden="true" />
          </Link>
        </CardContent>
      </Card>
    );
  }

  return null;
}

export default function CommandCenterPage() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [metricsKey, setMetricsKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getAgents(),
      getLeads({ limit: 1 }),
      listOrganizationSalesRuns({ limit: 1 }),
    ])
      .then(([agents, leads, salesRuns]) => {
        if (cancelled) return;
        setData({
          agents,
          leadTotal: leads.total,
          newLeads: leads.status_counts.NEW,
          waitingApproval: salesRuns.status_counts?.WAITING_APPROVAL ?? 0,
        });
        setError(null);
      })
      .catch(() => {
        if (!cancelled) setError("Command Center metrics could not be loaded.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [metricsKey]);

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Command Center"
        description="Run the sales workspace from one instruction, then review what still needs a person."
      />

      <WorkspaceCommand loading={loading} agents={data?.agents ?? []} />

      {!loading && data ? <CommandCenterNextStep data={data} /> : null}

      <section className="grid gap-5" aria-labelledby="pipeline-at-a-glance-heading">
        <SectionHeader
          id="pipeline-at-a-glance-heading"
          title="Pipeline at a glance"
          description="What is happening across your AI-assisted sales process."
        />
        <BusinessOverview
          loading={loading}
          leadTotal={data ? data.leadTotal : loading ? undefined : 0}
          newLeads={data?.newLeads ?? null}
          waitingApproval={data ? data.waitingApproval : loading ? undefined : 0}
        />
        {error ? (
          <p className="text-danger-text text-sm" role="alert">
            {error}
          </p>
        ) : null}
      </section>

      <AiWorkforceStatus loading={loading} agents={data?.agents ?? []} />

      <NeedsAttention
        onChanged={() => {
          setLoading(true);
          setMetricsKey((value) => value + 1);
        }}
      />

      <RecentActivity />

      <section className="grid gap-5" aria-labelledby="quick-actions-heading">
        <SectionHeader
          id="quick-actions-heading"
          title="Quick actions"
          description="Choose the next workspace for your team."
        />
        <QuickActions />
      </section>
    </div>
  );
}
