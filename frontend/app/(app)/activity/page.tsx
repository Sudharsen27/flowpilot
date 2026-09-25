"use client";

import { useCallback, useState } from "react";

import { ActivitySummary } from "@/components/activity/activity-summary";
import { ActivityWorkspace } from "@/components/activity/activity-workspace";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import type { ActivityListResponse } from "@/types/api";

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
        <ActivityWorkspace onSummary={onSummary} />
      </section>
    </div>
  );
}
