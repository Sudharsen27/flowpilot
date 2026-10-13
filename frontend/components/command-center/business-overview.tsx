import { ShieldCheck, Users } from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";
import { MetricStrip } from "@/components/data-display/metric-strip";

type BusinessOverviewProps = {
  loading?: boolean;
  leadTotal?: number | null;
  newLeads?: number | null;
  waitingApproval?: number | null;
};

export function BusinessOverview({
  loading = false,
  leadTotal = null,
  newLeads = null,
  waitingApproval = null,
}: BusinessOverviewProps) {
  return (
    <MetricStrip className="sm:grid-cols-2">
      <MetricCard
        label="Leads"
        value={leadTotal ?? undefined}
        description={
          newLeads === null
            ? "CRM records in this organization."
            : `${newLeads} with CRM status New.`
        }
        loading={loading}
        headingLevel={3}
        icon={<Users />}
      />
      <MetricCard
        label="Waiting for review"
        value={waitingApproval ?? undefined}
        description="Drafts waiting for a person to review."
        loading={loading}
        headingLevel={3}
        icon={<ShieldCheck />}
      />
    </MetricStrip>
  );
}
