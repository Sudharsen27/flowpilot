import { Bot, CheckCheck, ListTree, UserRound } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";
import type { ActivityEventType } from "@/types/api";

type ActivitySummaryProps = {
  loading?: boolean;
  total?: number;
  typeCounts?: Partial<Record<ActivityEventType, number>>;
};

export function ActivitySummary({
  loading = false,
  total,
  typeCounts,
}: ActivitySummaryProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label="Events"
        value={total}
        description="Organization events recorded so far."
        loading={loading}
        headingLevel={3}
        icon={<ListTree />}
      />
      <MetricCard
        label="AI actions"
        value={typeCounts?.AI_ACTION}
        description="Qualification, drafting, Sales Agent, and executions."
        loading={loading}
        headingLevel={3}
        icon={<Bot />}
      />
      <MetricCard
        label="Approvals"
        value={typeCounts?.APPROVAL}
        description="Draft approvals and rejections."
        loading={loading}
        headingLevel={3}
        icon={<CheckCheck />}
      />
      <MetricCard
        label="Human actions"
        value={typeCounts?.HUMAN_ACTION}
        description="Leads, review edits, sends, and follow-ups."
        loading={loading}
        headingLevel={3}
        icon={<UserRound />}
      />
    </div>
  );
}
