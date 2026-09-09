import { ApprovalSummary } from "@/components/approvals/approval-summary";
import { ApprovalsWorkspace } from "@/components/approvals/approvals-workspace";
import { HumanControl } from "@/components/approvals/human-control";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";

export default function ApprovalsPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Approvals"
        description="Review sensitive AI-proposed actions before anything is carried out."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Approval summary"
          description="Approval and risk signals will appear after agents can submit actions for review."
        />
        <ApprovalSummary />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Approval workspace"
          description="Review proposed actions, supporting context, risk, and intended outcomes."
        />
        <ApprovalsWorkspace />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Human control"
          description="A clear review boundary for actions that should not run autonomously."
        />
        <HumanControl />
      </section>
    </div>
  );
}
