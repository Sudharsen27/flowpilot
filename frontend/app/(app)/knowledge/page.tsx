"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { KnowledgeConnection } from "@/components/knowledge/knowledge-connection";
import { KnowledgeOverview } from "@/components/knowledge/knowledge-overview";
import { KnowledgeSearch } from "@/components/knowledge/knowledge-search";
import { KnowledgeSourceConcepts } from "@/components/knowledge/knowledge-source-concepts";
import { KnowledgeSourceList } from "@/components/knowledge/knowledge-source-list";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";

export default function KnowledgePage() {
  const [query, setQuery] = useState("");

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Knowledge"
        description="Knowledge connects business information to AI agents. Source management and indexing are coming soon."
        primaryAction={
          <div className="grid justify-items-end gap-1">
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
            <span className="text-muted-foreground text-xs">
              Available when source management is connected.
            </span>
          </div>
        }
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Knowledge overview"
          description="Source and indexing metrics become available when Knowledge sources are connected."
        />
        <KnowledgeOverview />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Knowledge sources"
          description="No sources are connected yet. Search applies only to supplied source rows and does not query a backend."
        />
        <KnowledgeSearch
          query={query}
          onQueryChange={setQuery}
          resultCount={0}
          sourceCount={0}
        />
        <KnowledgeSourceList sources={[]} searchQuery={query} />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Knowledge setup"
          description="Planned source categories for approved business context. None are connected."
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
