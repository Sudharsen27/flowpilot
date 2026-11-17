"use client";

import { Suspense, useCallback, useState } from "react";

import { ActivitySummary } from "@/components/activity/activity-summary";
import { ActivityWorkspace } from "@/components/activity/activity-workspace";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import type { ActivityListResponse } from "@/types/api";

function ActivityWorkspaceFallback() {
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
      <div className="border-border rounded-lg border p-4" role="status">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="mt-4 h-10 w-full" />
        <Skeleton className="mt-3 h-24 w-full" />
        <span className="sr-only">Loading activity workspace</span>
      </div>
      <div className="border-border rounded-lg border p-4">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="mt-4 h-40 w-full" />
      </div>
    </div>
  );
}

export default function ActivityPage() {
  const [summary, setSummary] = useState<ActivityListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const onSummary = useCallback((page: ActivityListResponse | null) => {
    setSummary(page);
    setLoading(false);
  }, []);

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Activity"
        description="See what is happening across your organization. This is an operational timeline, not a compliance audit log."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Activity summary"
          description="Counts reflect the current activity search and filters."
        />
        <ActivitySummary
          loading={loading && summary === null}
          total={summary?.total}
          typeCounts={summary?.type_counts}
        />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Activity workspace"
          description="Search, filter, and inspect real events from leads, Sales Agent work, email, and follow-ups."
        />
        <Suspense fallback={<ActivityWorkspaceFallback />}>
          <ActivityWorkspace onSummary={onSummary} />
        </Suspense>
      </section>
    </div>
  );
}
