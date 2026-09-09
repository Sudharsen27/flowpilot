import { CircleCheckBig, History } from "lucide-react";

import { AiWorkforceStatus } from "@/components/command-center/ai-workforce-status";
import { BusinessOverview } from "@/components/command-center/business-overview";
import { QuickActions } from "@/components/command-center/quick-actions";
import { EmptyState } from "@/components/empty-state";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";

export default function CommandCenterPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Command Center"
        description="See what needs attention, understand operational signals, and prepare FlowPilot to work across your business."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Business overview"
          description="Live signals will appear after operational data sources are connected."
        />
        <BusinessOverview />
      </section>

      <AiWorkforceStatus />

      <div className="grid gap-6 lg:grid-cols-2">
        <EmptyState
          className="h-full max-w-none"
          icon={<CircleCheckBig />}
          title="Needs attention"
          description="Nothing requires your review yet. Approvals and tasks will appear here when those systems are connected."
        />
        <EmptyState
          className="h-full max-w-none"
          icon={<History />}
          title="Recent activity"
          description="No business activity is available yet. Verified agent and workflow events will appear here once execution tracking exists."
        />
      </div>

      <section className="grid gap-5">
        <SectionHeader
          title="Quick actions"
          description="Move directly to an existing FlowPilot workspace."
        />
        <QuickActions />
      </section>
    </div>
  );
}
