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
  overdueFollowUps?: number | null;
};

export function BusinessOverview({
  loading = false,
  leadTotal = null,
  newLeads = null,
  waitingApproval = null,
  overdueFollowUps = null,
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
        unavailableLabel="Conversation history is not available yet."
        headingLevel={3}
        icon={<MessageSquareText />}
      />
      <MetricCard
        label="Appointments"
        unavailableLabel="Appointment scheduling is not available yet."
        headingLevel={3}
        icon={<CalendarCheck />}
      />
      <MetricCard
        label="Waiting for approval"
        value={waitingApproval ?? undefined}
        description={
          overdueFollowUps === null
            ? "Sales runs waiting for human draft review."
            : `${overdueFollowUps} follow-up${overdueFollowUps === 1 ? "" : "s"} overdue.`
        }
        loading={loading}
        headingLevel={3}
        icon={<ShieldCheck />}
      />
    </div>
  );
}
