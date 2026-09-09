import { InboxSummary } from "@/components/ai-inbox/inbox-summary";
import { InboxWorkspace } from "@/components/ai-inbox/inbox-workspace";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";

export default function InboxPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="AI Inbox"
        description="Bring customer conversations into one workspace for clear, coordinated follow-up."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Inbox summary"
          description="Live conversation signals will appear after a communication channel and conversation API are connected."
        />
        <InboxSummary />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Inbox workspace"
          description="Review conversations, customer context, AI assistance, and human handoffs in one place."
        />
        <InboxWorkspace />
      </section>
    </div>
  );
}
