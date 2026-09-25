import { CircleCheck, ClockAlert, UserPlus, Users } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";
import type { LeadListResponse } from "@/types/api";

type LeadOverviewProps = {
  summary?: LeadListResponse | null;
  loading?: boolean;
};

export function LeadOverview({ summary, loading = false }: LeadOverviewProps) {
  const total = summary?.status_counts
    ? Object.values(summary.status_counts).reduce((sum, count) => sum + count, 0)
    : undefined;
  const newCount = summary?.status_counts.NEW;
  const qualifiedCount = summary?.status_counts.QUALIFIED;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-live="polite">
      <MetricCard
        label="Total leads"
        value={total}
        description="All captured leads in this organization."
        unavailableLabel="No lead data"
        headingLevel={3}
        loading={loading}
        icon={<Users />}
        className="border-border bg-muted/25"
      />
      <MetricCard
        label="New leads"
        value={newCount}
        description="Leads still in New status."
        unavailableLabel="No lead data"
        headingLevel={3}
        loading={loading}
        icon={<UserPlus />}
        className="border-border bg-muted/25"
      />
      <MetricCard
        label="Qualified leads"
        value={qualifiedCount}
        description="Leads marked Qualified. This is a pipeline status, not an AI score."
        unavailableLabel="No qualified leads"
        headingLevel={3}
        loading={loading}
        icon={<CircleCheck />}
        className="border-border bg-muted/25"
      />
      <MetricCard
        label="Follow-up required"
        description="Overdue and upcoming follow-ups are listed in the Follow-ups section."
        unavailableLabel="See Follow-ups below for overdue and upcoming actions"
        headingLevel={3}
        icon={<ClockAlert />}
        className="border-border bg-muted/25"
      />
    </div>
  );
}
