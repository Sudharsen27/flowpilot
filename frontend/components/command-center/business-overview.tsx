import {
  CalendarCheck,
  MessageSquareText,
  ShieldCheck,
  Users,
} from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";

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
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
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
        label="Conversations"
        unavailableStatusLabel="Not available yet"
        unavailableLabel="Conversation history is not available yet."
        headingLevel={3}
        icon={<MessageSquareText />}
      />
      <MetricCard
        label="Appointments"
        unavailableStatusLabel="Not available yet"
        unavailableLabel="Appointment scheduling is not available yet."
        headingLevel={3}
        icon={<CalendarCheck />}
      />
      <MetricCard
        label="Waiting for review"
        value={waitingApproval ?? undefined}
        description="Sales runs with a draft ready for review."
        loading={loading}
        headingLevel={3}
        icon={<ShieldCheck />}
      />
    </div>
  );
}
