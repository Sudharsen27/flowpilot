import { Plus } from "lucide-react";

import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { WorkflowBlueprint } from "@/components/workflows/workflow-blueprint";
import { WorkflowConcepts } from "@/components/workflows/workflow-concepts";
import { WorkflowList } from "@/components/workflows/workflow-list";
import { WorkflowOverview } from "@/components/workflows/workflow-overview";

export default function WorkflowsPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Workflows"
        description="Connect business events, AI agents, conditions, approvals, and actions into controlled operating processes."
        primaryAction={
          <>
            <Button
              type="button"
              disabled
              aria-describedby="create-workflow-unavailable"
            >
              <Plus aria-hidden="true" />
              Create workflow
            </Button>
            <span id="create-workflow-unavailable" className="sr-only">
              Workflow creation is not available yet.
            </span>
          </>
        }
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Workflow overview"
          description="Workflow totals, operating status, and health will appear after persistence and execution are implemented."
        />
        <WorkflowOverview />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Configured workflows"
          description="Review workflow triggers, status, connected agents, and execution history."
        />
        <WorkflowList workflows={[]} />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Workflow blueprint"
          description="A product model for how future workflows can move from an event to a controlled outcome."
        />
        <WorkflowBlueprint />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Configuration concepts"
          description="Potential trigger and action categories for future workflow configuration."
        />
        <WorkflowConcepts />
      </section>
    </div>
  );
}
