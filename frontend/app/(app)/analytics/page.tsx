import { AnalyticsOverview } from "@/components/analytics/analytics-overview";
import {
  AnalyticsPanel,
  AnalyticsPanelGrid,
} from "@/components/analytics/analytics-panel";
import { AnalyticsSetup } from "@/components/analytics/analytics-setup";
import { AnalyticsToolbar } from "@/components/analytics/analytics-toolbar";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";

export default function AnalyticsPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Analytics"
        description="Understand FlowPilot performance and business outcomes as real activity is recorded."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Reporting period"
          description="Choose a date range and scope. These controls do not change analytics data yet."
        />
        <AnalyticsToolbar />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Overview"
          description="Key signals will appear after analytics aggregation is implemented."
        />
        <AnalyticsOverview />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Performance"
          description="Lead, conversation, agent, and workflow measurements are unavailable until real activity exists."
        />
        <AnalyticsPanelGrid>
          <AnalyticsPanel
            headingId="lead-performance-title"
            title="Lead performance"
            description="Future measurements for lead volume, qualification, conversion, and sources."
            metrics={[
              "Lead volume",
              "Qualification rate",
              "Conversion rate",
              "Lead sources",
            ]}
          />
          <AnalyticsPanel
            headingId="conversation-performance-title"
            title="Conversation performance"
            description="Future measurements for conversation volume, AI handling, handoffs, and response performance."
            metrics={[
              "Conversation volume",
              "AI handled conversations",
              "Human handoffs",
              "Response performance",
            ]}
          />
          <AnalyticsPanel
            headingId="agent-performance-title"
            title="AI agent performance"
            description="Future measurements for agent work. No agent execution is claimed."
            metrics={[
              "Tasks completed",
              "AI-handled conversations",
              "Escalations",
              "Success rate",
            ]}
          />
          <AnalyticsPanel
            headingId="workflow-performance-title"
            title="Workflow performance"
            description="Future measurements for workflow runs, success, failure, and approvals."
            metrics={[
              "Workflow runs",
              "Successful runs",
              "Failed runs",
              "Approval rate",
            ]}
          />
        </AnalyticsPanelGrid>
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Outcomes"
          description="Business outcome signals will appear after recorded activity can be measured."
        />
        <AnalyticsPanel
          headingId="outcomes-title"
          title="Business outcomes"
          description="Future measurements for qualified opportunities, appointments, follow-ups, and human interventions."
          metrics={[
            "Qualified opportunities",
            "Appointments booked",
            "Follow-ups completed",
            "Human interventions",
          ]}
        />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Setup and data trust"
          description="Analytics remain empty until FlowPilot records real business activity."
        />
        <AnalyticsSetup />
      </section>
    </div>
  );
}
