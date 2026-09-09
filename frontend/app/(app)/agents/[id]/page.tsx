import { Save } from "lucide-react";

import { AgentCapabilities } from "@/components/agents/agent-capabilities";
import { AgentCommunication } from "@/components/agents/agent-communication";
import { AgentConfigurationSidebar } from "@/components/agents/agent-configuration-sidebar";
import { AgentIdentityForm } from "@/components/agents/agent-identity-form";
import { AgentInstructions } from "@/components/agents/agent-instructions";
import { AgentResources } from "@/components/agents/agent-resources";
import { AgentSafety } from "@/components/agents/agent-safety";
import { StatePanel } from "@/components/data-display/state-panel";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";

export default function AgentDetailPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        breadcrumbs={[
          { label: "AI Agents", href: "/agents" },
          { label: "Agent configuration" },
        ]}
        title="Agent configuration"
        description="Set up an agent's identity, operating instructions, capabilities, resources, communication behavior, and human-control boundaries."
        secondaryActions={
          <StatusBadge status="draft" label="Configuration incomplete" />
        }
        primaryAction={
          <>
            <Button
              type="button"
              disabled
              aria-describedby="agent-save-unavailable"
            >
              <Save aria-hidden="true" />
              Save configuration
            </Button>
            <span id="agent-save-unavailable" className="sr-only">
              Saving is unavailable because agent persistence is not
              implemented.
            </span>
          </>
        }
      />

      <StatePanel
        kind="unavailable"
        className="max-w-none"
        title="Configuration is not connected"
        description="This workspace presents future configuration concepts only. No agent record is loaded, changes are not tracked, and nothing can be saved or executed."
      />

      <div
        data-slot="agent-detail-layout"
        className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]"
      >
        <div className="grid min-w-0 gap-6">
          <AgentIdentityForm />
          <AgentInstructions />
          <AgentCapabilities />
          <AgentResources />
          <AgentSafety />
          <AgentCommunication />
        </div>
        <AgentConfigurationSidebar />
      </div>
    </div>
  );
}
