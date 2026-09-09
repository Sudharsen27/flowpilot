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
        description="Connect FlowPilot with the business tools your teams already use so future agents and workflows can work across approved systems."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Integration overview"
          description="Connection, availability, health, and data-source signals will appear after integration support is implemented."
        />
        <IntegrationOverview />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Connection status"
          description="No external systems are connected to this organization."
        />
        <IntegrationSetupState />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Integration catalog"
          description="Explore planned integration concepts by category. These entries do not represent current product support."
        />
        <IntegrationCatalog />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Integration setup"
          description="A non-functional preview of the information a future connection flow may provide."
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
