"use client";

import { CircleCheckBig, History } from "lucide-react";
import { useEffect, useState } from "react";

import { AiWorkforceStatus } from "@/components/command-center/ai-workforce-status";
import { BusinessOverview } from "@/components/command-center/business-overview";
import { QuickActions } from "@/components/command-center/quick-actions";
import { EmptyState } from "@/components/empty-state";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { getAgents } from "@/lib/api/agents";
import { getFollowUpOperations, getLeads } from "@/lib/api/leads";
import { listOrganizationSalesRuns } from "@/lib/api/sales-runs";
import type { Agent } from "@/types/api";

type DashboardData = {
  agents: Agent[];
  leadTotal: number;
  newLeads: number;
  overdueFollowUps: number;
  waitingApproval: number;
};

export default function CommandCenterPage() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getAgents(),
      getLeads({ limit: 1 }),
      getFollowUpOperations({ limit: 1 }),
      listOrganizationSalesRuns({ status: "WAITING_APPROVAL", limit: 1 }),
    ])
      .then(([agents, leads, followUps, salesRuns]) => {
        if (cancelled) return;
        setData({
          agents,
          leadTotal: leads.total,
          newLeads: leads.status_counts.NEW,
          overdueFollowUps: followUps.summary.overdue,
          waitingApproval: salesRuns.total,
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
  }, []);

  const waiting = data?.waitingApproval ?? 0;
  const overdue = data?.overdueFollowUps ?? 0;

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Command Center"
        description="See what needs attention from live FlowPilot records. Conversations, appointments, and an organization-wide activity feed are not available yet."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Business overview"
          description="Lead counts are CRM records. Waiting for approval counts Sales runs that have a draft ready for human review."
        />
        <BusinessOverview
          loading={loading}
          leadTotal={data ? data.leadTotal : loading ? undefined : 0}
          newLeads={data?.newLeads ?? null}
          waitingApproval={data ? data.waitingApproval : loading ? undefined : 0}
          overdueFollowUps={data?.overdueFollowUps ?? null}
        />
        {error ? (
          <p className="text-danger-text text-sm" role="alert">
            {error}
          </p>
        ) : null}
      </section>

      <AiWorkforceStatus loading={loading} agents={data?.agents ?? []} />

      <div className="grid gap-6 lg:grid-cols-2">
        <EmptyState
          className="h-full max-w-none"
          icon={<CircleCheckBig />}
          title="Needs attention"
          description={
            waiting || overdue
              ? `${waiting} sales run${waiting === 1 ? "" : "s"} waiting for approval. ${overdue} overdue follow-up${overdue === 1 ? "" : "s"}.`
              : "No sales runs are waiting for approval, and there are no overdue follow-ups."
          }
        />
        <EmptyState
          className="h-full max-w-none"
          icon={<History />}
          title="Recent activity"
          description="An organization-wide activity feed is not available yet. Agent execution history and sales runs are on each agent detail page."
        />
      </div>

      <section className="grid gap-5">
        <SectionHeader
          title="Quick actions"
          description="Move directly to an existing FlowPilot workspace."
        />
        <QuickActions />
      </section>
    </div>
  );
}
