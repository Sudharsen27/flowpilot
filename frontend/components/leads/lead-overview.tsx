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
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label="Total leads"
        value={total}
        description="All captured leads in this organization."
        unavailableLabel="No lead data"
        headingLevel={3}
        loading={loading}
        icon={<Users />}
      />
      <MetricCard
        label="New leads"
        value={newCount}
        description="Leads still in New status."
        unavailableLabel="No lead data"
        headingLevel={3}
        loading={loading}
        icon={<UserPlus />}
      />
      <MetricCard
        label="Qualified leads"
        value={qualifiedCount}
        description="Leads marked Qualified. This is a pipeline status, not an AI score."
        unavailableLabel="No qualified leads"
        headingLevel={3}
        loading={loading}
        icon={<CircleCheck />}
      />
      <MetricCard
        label="Follow-up required"
        unavailableLabel="Follow-up tracking is not available yet"
        headingLevel={3}
        icon={<ClockAlert />}
      />
    </div>
  );
}
