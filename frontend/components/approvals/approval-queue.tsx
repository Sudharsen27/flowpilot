import { ClipboardCheck } from "lucide-react";

import { RiskBadge, type RiskLevel } from "@/components/approvals/risk-badge";
import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";
import { statusPresentation } from "@/lib/status";

export type ApprovalStatus = "pending" | "approved" | "rejected";

export type ApprovalQueueItem = {
  id: string;
  action: string;
  agentName: string;
  requestedAction: string;
  riskLevel: RiskLevel;
  requestedTimeLabel?: string;
  status: ApprovalStatus;
};

type ApprovalQueueProps = {
  approvals: ApprovalQueueItem[];
  selectedId?: string;
  onSelect?: (approval: ApprovalQueueItem) => void;
};

const approvalStatusCodes: Record<ApprovalStatus, string> = {
  pending: "PENDING",
  approved: "APPROVED",
  rejected: "REJECTED",
};

const approvalStatusLabels: Record<ApprovalStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

export function ApprovalQueue({
  approvals,
  selectedId,
  onSelect,
}: ApprovalQueueProps) {
  if (approvals.length === 0) {
    return (
      <EmptyState
        compact
        icon={<ClipboardCheck />}
        className="max-w-none rounded-none border-x-0 border-b-0 shadow-none"
        title="No approval requests"
        description="Approval requests will appear here when FlowPilot agents begin proposing actions that require human authorization."
      />
    );
  }

  return (
    <ul
      aria-label="Approval queue"
      className="divide-border divide-y"
      data-slot="approval-queue"
    >
      {approvals.map((approval) => {
        const status = statusPresentation(
          approvalStatusCodes[approval.status],
          approvalStatusLabels[approval.status],
        );
        const isSelected = selectedId === approval.id;

        return (
          <li key={approval.id}>
            <button
              type="button"
              className={cn(
                "hover:bg-surface-subtle focus-visible:ring-ring/40 w-full p-4 text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-inset",
                isSelected && "bg-surface-subtle",
              )}
              aria-pressed={isSelected}
              onClick={() => onSelect?.(approval)}
            >
              <span className="flex items-start justify-between gap-3">
                <span className="min-w-0">
                  <span className="block text-sm font-medium">
                    {approval.action}
                  </span>
                  <span className="text-muted-foreground mt-0.5 block truncate text-xs">
                    Proposed by {approval.agentName}
                  </span>
                </span>
                {approval.requestedTimeLabel ? (
                  <span className="text-muted-foreground shrink-0 text-xs">
                    {approval.requestedTimeLabel}
                  </span>
                ) : null}
              </span>
              <span className="text-muted-foreground mt-3 line-clamp-2 block text-sm leading-5">
                {approval.requestedAction}
              </span>
              <span className="mt-3 flex flex-wrap gap-2">
                <RiskBadge level={approval.riskLevel} />
                <StatusBadge status={status.status} label={status.label} />
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
