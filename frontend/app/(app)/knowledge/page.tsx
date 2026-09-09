import { Plus } from "lucide-react";

import { KnowledgeConnection } from "@/components/knowledge/knowledge-connection";
import { KnowledgeOverview } from "@/components/knowledge/knowledge-overview";
import { KnowledgeSearch } from "@/components/knowledge/knowledge-search";
import { KnowledgeSourceConcepts } from "@/components/knowledge/knowledge-source-concepts";
import { KnowledgeSourceList } from "@/components/knowledge/knowledge-source-list";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";

export default function KnowledgePage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Knowledge"
        description="Give FlowPilot agents access to the business-specific information they need to understand enquiries and work accurately."
        primaryAction={
          <>
            <Button
              type="button"
              disabled
              aria-describedby="add-knowledge-unavailable"
            >
              <Plus aria-hidden="true" />
              Add source
            </Button>
            <span id="add-knowledge-unavailable" className="sr-only">
              Adding knowledge sources is not available yet.
            </span>
          </>
        }
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Knowledge overview"
          description="Source, document, and indexing signals will appear after knowledge ingestion is implemented."
        />
        <KnowledgeOverview />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Knowledge sources"
          description="Manage the business information that may eventually provide context to AI agents."
        />
        <KnowledgeSearch />
        <KnowledgeSourceList sources={[]} />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Knowledge setup"
          description="Future source categories for providing approved business context. None are connected."
        />
        <KnowledgeSourceConcepts />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="AI agent connection"
          description="A non-functional model of how business knowledge may eventually support agent responses and actions."
        />
        <KnowledgeConnection />
      </section>
    </div>
  );
}
