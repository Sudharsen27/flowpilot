import { Archive, CheckCheck, Clock3, MessageCircle } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";
import type { InboxConversationState } from "@/types/api";

type InboxSummaryProps = {
  loading?: boolean;
  stateCounts?: Partial<Record<InboxConversationState, number>>;
  needsApprovalCount?: number;
};

export function InboxSummary({
  loading = false,
  stateCounts,
  needsApprovalCount,
}: InboxSummaryProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label="Open conversations"
        value={stateCounts?.OPEN}
        description="Conversations still in progress."
        unavailableLabel="No open conversations"
        loading={loading}
        headingLevel={3}
        icon={<MessageCircle />}
      />
      <MetricCard
        label="Waiting for approval"
        value={stateCounts?.NEEDS_APPROVAL}
        description="Drafts or Sales Runs waiting for human review."
        unavailableLabel="Nothing waiting"
        loading={loading}
        headingLevel={3}
        icon={<Clock3 />}
      />
      <MetricCard
        label="Closed"
        value={stateCounts?.CLOSED}
        description="Converted, unqualified, or completed outreach."
        unavailableLabel="No closed conversations"
        loading={loading}
        headingLevel={3}
        icon={<Archive />}
      />
      <MetricCard
        label="Needs human review"
        value={needsApprovalCount}
        description="Items that require approval before send."
        unavailableLabel="No review needed"
        loading={loading}
        headingLevel={3}
        icon={<CheckCheck />}
      />
    </div>
  );
}
