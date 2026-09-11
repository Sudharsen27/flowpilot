import { CalendarClock, CalendarDays, CheckCircle2, ClockAlert } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";
import type { FollowUpOperationsSummary } from "@/types/api";

type FollowUpsOverviewProps = {
  summary?: FollowUpOperationsSummary | null;
  loading?: boolean;
};

/**
 * Counts come straight from the API and cover the whole organization, not just
 * the visible page. Values stay blank until real data arrives.
 */
export function FollowUpsOverview({
  summary,
  loading = false,
}: FollowUpsOverviewProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label="Overdue"
        value={summary ? summary.overdue : undefined}
        description="Pending and past due"
        unavailableLabel="No follow-up data yet"
        loading={loading}
        headingLevel={3}
        icon={<ClockAlert />}
      />
      <MetricCard
        label="Today"
        value={summary ? summary.due_today : undefined}
        description="Pending and due today (UTC)"
        unavailableLabel="No follow-up data yet"
        loading={loading}
        headingLevel={3}
        icon={<CalendarDays />}
      />
      <MetricCard
        label="Upcoming"
        value={summary ? summary.upcoming : undefined}
        description="Pending and due later"
        unavailableLabel="No follow-up data yet"
        loading={loading}
        headingLevel={3}
        icon={<CalendarClock />}
      />
      <MetricCard
        label="Completed"
        value={summary ? summary.completed : undefined}
        description={
          summary
            ? `${summary.cancelled} cancelled`
            : "Completed follow-ups"
        }
        unavailableLabel="No follow-up data yet"
        loading={loading}
        headingLevel={3}
        icon={<CheckCircle2 />}
      />
    </div>
  );
}
