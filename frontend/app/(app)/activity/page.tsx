import { ActivityConcepts } from "@/components/activity/activity-concepts";
import { ActivitySummary } from "@/components/activity/activity-summary";
import { ActivityWorkspace } from "@/components/activity/activity-workspace";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";

export default function ActivityPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Activity"
        description="Review a chronological record of important actions and events across FlowPilot."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Activity summary"
          description="Event and actor signals will appear after activity ingestion and persistence are implemented."
        />
        <ActivitySummary />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Activity workspace"
          description="Search the future timeline and inspect the source, status, and context of recorded events."
        />
        <ActivityWorkspace />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Event and audit context"
          description="A clear classification model for understanding future activity records."
        />
        <ActivityConcepts />
      </section>
    </div>
  );
}
