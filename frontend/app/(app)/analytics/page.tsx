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
        description="Analytics is coming soon. Reporting metrics and performance insights will appear here when analytics data is available."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Reporting period"
          description="Preview reporting controls. They are unavailable until analytics data is connected."
        />
        <AnalyticsToolbar />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Overview"
          description="Overview metrics are unavailable until analytics data is connected."
        />
        <AnalyticsOverview />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Performance"
          description="Performance reporting will be available when analytics data is connected."
        />
        <AnalyticsPanelGrid>
          <AnalyticsPanel
            headingId="lead-performance-title"
            title="Lead performance"
            description="Planned measurements for lead volume, qualification, conversion, and sources."
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
            description="Planned measurements for conversation volume, AI handling, handoffs, and response performance."
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
            description="Planned measurements for agent work. No agent execution is claimed."
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
            description="Planned measurements for workflow runs, success, failure, and approvals."
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
          description="Outcome reporting will be available when analytics aggregation is available."
        />
        <AnalyticsPanel
          headingId="outcomes-title"
          title="Business outcomes"
          description="Planned measurements for qualified opportunities, appointments, follow-ups, and human interventions."
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
          description="Analytics is planned; no reporting data is connected yet."
        />
        <AnalyticsSetup />
      </section>
    </div>
  );
}
