import { Bot, CheckCheck, CircleDollarSign, Handshake, Trophy, Users } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";
import { MetricStrip } from "@/components/data-display/metric-strip";
import { formatMoney, formatMoneyCompact } from "@/lib/money";
import type { AgentExecutionStatus, PipelineSummary } from "@/types/api";

type DashboardKpisProps = {
  loading: boolean;
  leadTotal: number | null | undefined;
  newLeads: number | null;
  waitingApproval: number | null | undefined;
  /** undefined while loading, null when the pipeline summary is unavailable. */
  summary: PipelineSummary | null | undefined;
  executionCounts: Partial<Record<AgentExecutionStatus, number>> | null | undefined;
};

export function MoneyValue({ amount, currency }: { amount: string; currency: string }) {
  // Compact on the tile; the exact amount is the accessible name and tooltip.
  const exact = formatMoney(amount, currency);
  return (
    <span title={exact} aria-label={exact}>
      {formatMoneyCompact(amount, currency)}
    </span>
  );
}

/** Headline figures from real APIs only; a missing source shows as unavailable, never 0. */
export function DashboardKpis({
  loading,
  leadTotal,
  newLeads,
  waitingApproval,
  summary,
  executionCounts,
}: DashboardKpisProps) {
  const summaryLoading = summary === undefined;
  const runs = executionCounts
    ? Object.values(executionCounts).reduce((total, value) => total + (value ?? 0), 0)
    : null;
  return (
    <MetricStrip className="sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
      <MetricCard
        headingLevel={3}
        label="Leads"
        icon={<Users />}
        loading={loading}
        value={leadTotal ?? undefined}
        description={
          newLeads === null ? "CRM records in this organization." : `${newLeads} with CRM status New.`
        }
        unavailableLabel="Lead counts are unavailable."
      />
      <MetricCard
        headingLevel={3}
        label="Open deals"
        icon={<Handshake />}
        loading={summaryLoading}
        value={summary ? summary.open.count : undefined}
        description={
          summary
            ? summary.overdue_open.count > 0
              ? `${summary.overdue_open.count} past expected close`
              : "None past expected close"
            : undefined
        }
        unavailableLabel="Deal figures are unavailable."
      />
      <MetricCard
        headingLevel={3}
        label="Pipeline value"
        icon={<CircleDollarSign />}
        loading={summaryLoading}
        value={
          summary ? <MoneyValue amount={summary.open.total_amount} currency={summary.currency} /> : undefined
        }
        description={
          summary
            ? `Weighted ${formatMoney(summary.open.weighted_amount, summary.currency)}`
            : undefined
        }
        unavailableLabel="Deal figures are unavailable."
      />
      <MetricCard
        headingLevel={3}
        label="Won deals"
        icon={<Trophy />}
        loading={summaryLoading}
        value={summary ? summary.won.count : undefined}
        description={summary ? `${formatMoney(summary.won.total_amount, summary.currency)} won to date` : undefined}
        unavailableLabel="Deal figures are unavailable."
      />
      <MetricCard
        headingLevel={3}
        label="Waiting for review"
        icon={<CheckCheck />}
        loading={loading}
        value={waitingApproval ?? undefined}
        description="Drafts waiting for a person to review."
        unavailableLabel="Approval counts are unavailable."
      />
      <MetricCard
        headingLevel={3}
        label="Agent runs"
        icon={<Bot />}
        loading={executionCounts === undefined}
        value={runs ?? undefined}
        description={
          executionCounts
            ? `${executionCounts.RUNNING ?? 0} running · ${executionCounts.FAILED ?? 0} failed`
            : undefined
        }
        unavailableLabel="Run counts are unavailable."
      />
    </MetricStrip>
  );
}
