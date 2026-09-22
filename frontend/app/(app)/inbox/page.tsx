"use client";

import { useCallback, useState } from "react";

import { InboxSummary } from "@/components/ai-inbox/inbox-summary";
import { InboxWorkspace } from "@/components/ai-inbox/inbox-workspace";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import type { InboxListResponse } from "@/types/api";

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
        description="Review sales conversation history — enquiries, drafts, email, Sales Runs, and follow-ups — in one place."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Inbox summary"
          description="Counts come from the current Inbox filters for this organization."
        />
        <InboxSummary
          loading={loading && summary === null}
          stateCounts={summary?.state_counts}
          needsApprovalCount={summary?.needs_approval_count}
        />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Inbox workspace"
          description="Select a lead to inspect its timeline and context. Sending stays on the Lead and Sales Agent screens."
        />
        <InboxWorkspace onSummary={onSummary} />
      </section>
    </div>
  );
}
