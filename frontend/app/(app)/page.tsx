"use client";

import { useEffect, useState } from "react";

import { AiWorkforceStatus } from "@/components/command-center/ai-workforce-status";
import { BusinessOverview } from "@/components/command-center/business-overview";
import { NeedsAttention } from "@/components/command-center/needs-attention";
import { QuickActions } from "@/components/command-center/quick-actions";
import { RecentActivity } from "@/components/command-center/recent-activity";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
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
        description="An operational overview of your sales pipeline, AI workforce, and work that needs attention."
      />

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
