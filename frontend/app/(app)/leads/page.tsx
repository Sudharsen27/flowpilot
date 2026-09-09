import { LeadOverview } from "@/components/leads/lead-overview";
import { LeadsTable } from "@/components/leads/leads-table";
import { LeadsToolbar } from "@/components/leads/leads-toolbar";
import { QualificationReadiness } from "@/components/leads/qualification-readiness";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";

export default function LeadsPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Leads"
        description="Capture, qualify, and follow up with enquiries as they move through your sales process."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Lead overview"
          description="Live lead signals will appear after a lead source and data API are connected."
        />
        <LeadOverview />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Lead directory"
          description="Search and review leads received from your connected business channels."
        />
        <LeadsToolbar />
        <LeadsTable leads={[]} />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="AI qualification"
          description="Understand qualification outcomes using explicit status, score, and explanation fields."
        />
        <QualificationReadiness />
      </section>
    </div>
  );
}
