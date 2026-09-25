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
        description="Workflows are a planned way to connect business events, AI agents, approvals, and actions into controlled operating processes."
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
              Workflow creation is planned and is not available yet.
            </span>
          </>
        }
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Workflow overview"
          description="Workflow metrics are unavailable until workflows can be configured and executed."
        />
        <WorkflowOverview />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Configured workflows"
          description="No workflows are configured. The list will support workflow records when persistence is available."
        />
        <WorkflowList workflows={[]} />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Workflow blueprint"
          description="Explore the planned model for moving from an event to a controlled outcome."
        />
        <WorkflowBlueprint />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Configuration concepts"
          description="Planned trigger and action categories. None are live configuration controls."
        />
        <WorkflowConcepts />
      </section>
    </div>
  );
}
