import { IntegrationCatalog } from "@/components/integrations/integration-catalog";
import { IntegrationConnection } from "@/components/integrations/integration-connection";
import { IntegrationOverview } from "@/components/integrations/integration-overview";
import { IntegrationSetupConcept } from "@/components/integrations/integration-setup-concept";
import { IntegrationSetupState } from "@/components/integrations/integration-setup-state";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";

export default function IntegrationsPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Integrations"
        description="Connect FlowPilot with the tools your team uses. Integration connections are coming soon."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Integration overview"
          description="Live connection metrics are not available until integration connections are supported."
        />
        <IntegrationOverview />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Connection status"
          description="No external systems are connected. Existing links below remain available while integrations are planned."
        />
        <IntegrationSetupState />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Integration catalog"
          description="Explore the 11 planned provider concepts. None are available to connect yet."
        />
        <IntegrationCatalog />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Integration setup"
          description="A preview of the setup information a future connection flow may provide."
        />
        <IntegrationSetupConcept />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Agents, workflows, and trust"
          description="How future connections may fit into FlowPilot while remaining subject to explicit organizational controls."
        />
        <IntegrationConnection />
      </section>
    </div>
  );
}
