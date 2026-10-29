"use client";

import { Suspense } from "react";

import { OrganizationExecutionsWorkspace } from "@/components/agents/organization-executions-workspace";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";

function OrganizationExecutionsFallback() {
  return (
    <div className="grid gap-4" role="status">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {Array.from({ length: 5 }, (_, index) => (
          <Skeleton key={index} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-64 w-full" />
      <span className="sr-only">Loading agent executions</span>
    </div>
  );
}

export default function AgentExecutionsPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        breadcrumbs={[
          { label: "AI Agents", href: "/agents" },
          { label: "Agent runs" },
        ]}
        title="Agent runs"
        description="Every agent execution across your organization, with status, the agent and lead involved, and any failure. This view is read-only."
      />
      <Suspense fallback={<OrganizationExecutionsFallback />}>
        <OrganizationExecutionsWorkspace />
      </Suspense>
    </div>
  );
}
