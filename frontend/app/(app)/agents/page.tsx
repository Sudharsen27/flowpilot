import { Plus } from "lucide-react";

import { AgentBlueprints } from "@/components/agents/agent-blueprints";
import { AgentGrid } from "@/components/agents/agent-grid";
import { AgentOverview } from "@/components/agents/agent-overview";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";

export default function AgentsPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="AI Agents"
        description="Configure AI workers that can help execute clearly defined business tasks within controlled boundaries."
        primaryAction={
          <>
            <Button
              type="button"
              disabled
              aria-describedby="create-agent-unavailable"
            >
              <Plus aria-hidden="true" />
              Create agent
            </Button>
            <span id="create-agent-unavailable" className="sr-only">
              Agent creation is not available yet.
            </span>
          </>
        }
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Agent overview"
          description="Agent totals, status, and health will appear after agent persistence and monitoring are available."
        />
        <AgentOverview />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Configured agents"
          description="Manage each agent's purpose, capabilities, configuration, and operating status."
        />
        <AgentGrid agents={[]} />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Agent blueprints"
          description="Planned role and capability concepts for future configuration. These are not active agents."
        />
        <AgentBlueprints />
      </section>
    </div>
  );
}
