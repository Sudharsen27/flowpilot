"use client";

import { List, Plus } from "lucide-react";
import Link from "next/link";

import { PipelineBoard } from "@/components/deals/pipeline-board";
import { PageHeader } from "@/components/page-header";
import { buttonVariants } from "@/components/ui/button";

export default function PipelinePage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        breadcrumbs={[{ label: "Deals", href: "/deals" }, { label: "Pipeline" }]}
        title="Pipeline"
        description="Every deal by stage. Column totals come from your saved deals, not estimates."
        secondaryActions={
          <Link href="/deals" className={buttonVariants({ variant: "outline" })}>
            <List aria-hidden="true" />
            Table view
          </Link>
        }
        primaryAction={
          <Link href="/deals?create=1" className={buttonVariants({ variant: "default" })}>
            <Plus aria-hidden="true" />
            New deal
          </Link>
        }
      />
      <PipelineBoard />
    </div>
  );
}
