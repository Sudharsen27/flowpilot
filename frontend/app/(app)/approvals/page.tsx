"use client";

import { Suspense, useCallback, useState } from "react";

import { ApprovalSummary } from "@/components/approvals/approval-summary";
import { ApprovalsWorkspace } from "@/components/approvals/approvals-workspace";
import {
  type ApprovalDecisionState,
  HumanControl,
} from "@/components/approvals/human-control";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import type { ApprovalListResponse, ApprovalQueueStatus } from "@/types/api";

function ApprovalsWorkspaceFallback() {
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
      <div className="border-border rounded-lg border p-4" role="status">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="mt-4 h-10 w-full" />
        <Skeleton className="mt-3 h-24 w-full" />
        <span className="sr-only">Loading approvals workspace</span>
      </div>
      <div className="border-border rounded-lg border p-4">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="mt-4 h-40 w-full" />
      </div>
    </div>
  );
}

export default function ApprovalsPage() {
  const [loading, setLoading] = useState(true);
  const [activeStatus, setActiveStatus] =
    useState<ApprovalQueueStatus>("pending");
  const [totals, setTotals] = useState<
    Partial<Record<ApprovalQueueStatus, number | null>>
  >({});
  const [decision, setDecision] = useState<ApprovalDecisionState>("idle");

  const onSummary = useCallback(
    (page: ApprovalListResponse | null, status: ApprovalQueueStatus) => {
      setActiveStatus(status);
      setLoading(false);
      if (page) {
        setTotals((current) => ({ ...current, [status]: page.total }));
      }
    },
    [],
  );

  const onDecisionChange = useCallback((next: ApprovalDecisionState) => {
    setDecision(next);
  }, []);

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Approvals"
        description="Review the draft the agent prepared. Nothing is sent until you approve it."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Needs your review"
          description="Drafts waiting on a person in this organization."
        />
        <ApprovalSummary
          loading={loading}
          activeStatus={activeStatus}
          totals={totals}
        />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Approval workspace"
          description="Read the enquiry and the draft, then approve, edit, reject, or send."
        />
        <Suspense fallback={<ApprovalsWorkspaceFallback />}>
          <ApprovalsWorkspace
            onSummary={onSummary}
            onDecisionChange={onDecisionChange}
          />
        </Suspense>
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Human control"
          description="Approving a draft does not send it. Sending is a separate decision."
        />
        <HumanControl decision={decision} />
      </section>
    </div>
  );
}
