import {
  Bot,
  CalendarCheck,
  MessageSquareText,
  UserCheck,
  UserRoundCheck,
  Users,
} from "lucide-react";

import { MetricCard } from "@/components/data-display/metric-card";
import { MetricStrip } from "@/components/data-display/metric-strip";
import type { AnalyticsSummary } from "@/types/api";

type AnalyticsOverviewProps = {
  summary: AnalyticsSummary | null;
  loading: boolean;
};

export function AnalyticsOverview({ summary, loading }: AnalyticsOverviewProps) {
  const totals = summary?.totals;
  const metrics = [
    {
      label: "Leads created",
      value: totals?.leads_created,
      description: "New leads from every channel in this period.",
      icon: Users,
    },
    {
      label: "Qualified leads",
      value: totals?.leads_qualified,
      description: "Leads the AI assessed as qualified at least once.",
      icon: UserCheck,
    },
    {
      label: "Customer replies",
      value: totals?.customer_replies,
      description: "Inbound customer emails received.",
      icon: MessageSquareText,
    },
    {
      label: "AI handled",
      value: totals ? totals.ai_analyses + totals.ai_drafts : undefined,
      description: "AI analyses plus AI reply drafts completed.",
      icon: Bot,
    },
    {
      label: "Human handoffs",
      value: totals?.human_handoffs,
      description: "Times a lead was flagged for a person to review.",
      icon: UserRoundCheck,
    },
  ];

  return (
    <MetricStrip className="sm:grid-cols-2 xl:grid-cols-3">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <MetricCard
            key={metric.label}
            label={metric.label}
            value={metric.value?.toLocaleString()}
            description={metric.description}
            loading={loading}
            unavailableLabel="Not available right now"
            headingLevel={3}
            icon={<Icon />}
          />
        );
      })}
      <MetricCard
        label="Appointments"
        unavailableLabel="Needs a calendar integration. FlowPilot does not book appointments yet."
        unavailableStatusLabel="Not connected"
        headingLevel={3}
        icon={<CalendarCheck />}
      />
    </MetricStrip>
  );
}
