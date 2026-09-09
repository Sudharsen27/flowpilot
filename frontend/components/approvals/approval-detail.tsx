import {
  ArrowLeft,
  Check,
  ClipboardList,
  ShieldQuestion,
  X,
} from "lucide-react";

import type { ApprovalStatus } from "@/components/approvals/approval-queue";
import { RiskBadge, type RiskLevel } from "@/components/approvals/risk-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";

export type ApprovalDetailData = {
  id: string;
  action: string;
  requestedAction: string;
  reason: string;
  agentName: string;
  context: string;
  riskLevel: RiskLevel;
  intendedOutcome: string;
  status: ApprovalStatus;
};

type ApprovalDetailProps = {
  approval?: ApprovalDetailData;
  onBack?: () => void;
};

const statusPresentation: Record<
  ApprovalStatus,
  { status: StatusValue; label: string }
> = {
  pending: { status: "pending", label: "Pending" },
  approved: { status: "success", label: "Approved" },
  rejected: { status: "failed", label: "Rejected" },
};

type DetailFieldProps = {
  label: string;
  value?: string;
};

function DetailField({ label, value }: DetailFieldProps) {
  return (
    <div className="grid gap-1.5">
      <dt className="text-muted-foreground text-xs font-medium">{label}</dt>
      <dd className="text-sm leading-6">{value ?? "No approval selected."}</dd>
    </div>
  );
}

export function ApprovalDetail({ approval, onBack }: ApprovalDetailProps) {
  const status = approval ? statusPresentation[approval.status] : null;

  return (
    <Card
      as="section"
      className="flex min-h-[38rem] min-w-0 flex-col overflow-hidden"
      aria-labelledby="approval-detail-title"
    >
      <header className="border-border flex flex-wrap items-start justify-between gap-3 border-b px-4 py-4 sm:px-5">
        <div className="flex min-w-0 items-start gap-2">
          {onBack ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="Back to approval queue"
              onClick={onBack}
            >
              <ArrowLeft aria-hidden="true" />
            </Button>
          ) : null}
          <div className="min-w-0">
            <h3
              id="approval-detail-title"
              className="text-base font-medium tracking-tight"
            >
              {approval?.action ?? "Approval detail"}
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Review the proposed action and its context before deciding.
            </p>
          </div>
        </div>
        {status ? (
          <StatusBadge status={status.status} label={status.label} />
        ) : (
          <StatusBadge status="draft" label="Unavailable" />
        )}
      </header>

      <div className="flex flex-1 flex-col">
        {!approval ? (
          <section
            className="border-border flex flex-col items-center justify-center border-b px-6 py-10 text-center"
            aria-labelledby="approval-selection-title"
          >
            <div
              className="bg-muted text-muted-foreground flex size-10 items-center justify-center rounded-lg"
              aria-hidden="true"
            >
              <ClipboardList className="size-5" />
            </div>
            <h4
              id="approval-selection-title"
              className="mt-4 text-sm font-medium"
            >
              No approval selected
            </h4>
            <p className="text-muted-foreground mt-1.5 max-w-sm text-sm leading-6">
              Review details will appear here when a real approval request is
              available and selected.
            </p>
          </section>
        ) : null}

        <div className="grid flex-1 gap-6 p-5 sm:p-6 xl:grid-cols-2">
          <section aria-labelledby="proposed-action-title">
            <div className="flex items-center gap-2">
              <ClipboardList
                className="text-muted-foreground size-4"
                aria-hidden="true"
              />
              <h4 id="proposed-action-title" className="text-sm font-medium">
                Proposed action
              </h4>
            </div>
            <dl className="mt-4 grid gap-5">
              <DetailField
                label="What the AI wants to do"
                value={approval?.requestedAction}
              />
              <DetailField
                label="Why this was proposed"
                value={approval?.reason}
              />
              <DetailField label="Proposed by" value={approval?.agentName} />
            </dl>
          </section>

          <section aria-labelledby="decision-context-title">
            <div className="flex items-center gap-2">
              <ShieldQuestion
                className="text-muted-foreground size-4"
                aria-hidden="true"
              />
              <h4 id="decision-context-title" className="text-sm font-medium">
                Decision context
              </h4>
            </div>
            <dl className="mt-4 grid gap-5">
              <DetailField label="Relevant context" value={approval?.context} />
              <div className="grid gap-1.5">
                <dt className="text-muted-foreground text-xs font-medium">
                  Risk level
                </dt>
                <dd>
                  {approval ? (
                    <RiskBadge level={approval.riskLevel} />
                  ) : (
                    <StatusBadge status="draft" label="Unavailable" />
                  )}
                </dd>
              </div>
              <DetailField
                label="Intended outcome"
                value={approval?.intendedOutcome}
              />
            </dl>
          </section>
        </div>
      </div>

      <footer className="border-border bg-surface-subtle flex flex-wrap justify-end gap-2 border-t p-4">
        <Button type="button" variant="outline" disabled>
          <X aria-hidden="true" />
          Reject action
        </Button>
        <Button type="button" disabled>
          <Check aria-hidden="true" />
          Approve action
        </Button>
      </footer>
    </Card>
  );
}
