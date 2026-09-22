"use client";

import { Suspense, useCallback, useState } from "react";

import { ApprovalSummary } from "@/components/approvals/approval-summary";
import { ApprovalsWorkspace } from "@/components/approvals/approvals-workspace";
import { HumanControl } from "@/components/approvals/human-control";
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

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Approvals"
        description="What does FlowPilot need you to decide right now? Review AI responses before anything is sent."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Approval summary"
          description="Counts reflect the active filter after the Approval Center loads from the API."
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
          description="Review the customer enquiry, the AI response, and take Approve, Reject, Edit, or Send actions."
        />
        <Suspense fallback={<ApprovalsWorkspaceFallback />}>
          <ApprovalsWorkspace onSummary={onSummary} />
        </Suspense>
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Human control"
          description="Sensitive customer communication stays under human review."
        />
        <HumanControl />
      </section>
    </div>
  );
}
