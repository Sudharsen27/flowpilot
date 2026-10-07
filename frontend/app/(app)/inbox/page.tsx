"use client";

import { Suspense, useCallback, useState } from "react";

import { InboxSummary } from "@/components/ai-inbox/inbox-summary";
import { InboxWorkspace } from "@/components/ai-inbox/inbox-workspace";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import type { InboxListResponse } from "@/types/api";

function InboxWorkspaceFallback() {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
      <div className="border-border rounded-lg border p-4" role="status">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="mt-4 h-10 w-full" />
        <Skeleton className="mt-3 h-24 w-full" />
        <Skeleton className="mt-3 h-24 w-full" />
        <span className="sr-only">Loading inbox workspace</span>
      </div>
      <div className="border-border rounded-lg border p-4">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="mt-4 h-40 w-full" />
      </div>
    </div>
  );
}

export default function InboxPage() {
  const [summary, setSummary] = useState<InboxListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const onSummary = useCallback((page: InboxListResponse | null) => {
    setSummary(page);
    setLoading(false);
  }, []);

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="AI Inbox"
        description="See what the customer asked and what the agent prepared. Sending still happens from the lead, after approval."
      />

      <InboxSummary
        loading={loading && summary === null}
        stateCounts={summary?.state_counts}
        needsApprovalCount={summary?.needs_approval_count}
      />

      <Suspense fallback={<InboxWorkspaceFallback />}>
        <InboxWorkspace onSummary={onSummary} />
      </Suspense>
    </div>
  );
}
