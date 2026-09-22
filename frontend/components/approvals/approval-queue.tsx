import type { ReactNode } from "react";
import { ClipboardCheck } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { RelativeTime } from "@/components/ui/relative-time";
import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";
import type { ApprovalQueueItem } from "@/types/api";

type ApprovalQueueProps = {
  approvals: ApprovalQueueItem[];
  selectedId?: string | null;
  onSelect?: (approval: ApprovalQueueItem) => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
};

function previewText(value: string | null | undefined) {
  if (!value) return "No AI response yet";
  const cleaned = value.replace(/\s+/g, " ").trim();
  if (!cleaned) return "No AI response yet";
  return cleaned.length > 120 ? `${cleaned.slice(0, 119)}…` : cleaned;
}

function queueStatus(approval: ApprovalQueueItem): {
  status: StatusValue;
  label: string;
} {
  if (approval.email?.status === "SENT") {
    return { status: "success", label: "Response sent" };
  }
  if (approval.draft.review_status === "APPROVED") {
    return { status: "success", label: "Approved — ready to send" };
  }
  if (approval.draft.review_status === "REJECTED") {
    return { status: "failed", label: "Response rejected" };
  }
  if (approval.needs_approval) {
    return { status: "warning", label: "Needs your review" };
  }
  return { status: "draft", label: "In review" };
}

export function ApprovalQueue({
  approvals,
  selectedId,
  onSelect,
  emptyTitle = "You're all caught up.",
  emptyDescription = "No responses are waiting for your review.",
  emptyAction,
}: ApprovalQueueProps) {
  if (approvals.length === 0) {
    return (
      <EmptyState
        compact
        icon={<ClipboardCheck />}
        className="max-w-none rounded-none border-x-0 border-b-0 shadow-none"
        title={emptyTitle}
        description={emptyDescription}
        action={emptyAction}
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
        const status = queueStatus(approval);
        const isSelected = selectedId === approval.draft_id;
        const customerName = approval.lead.name.trim() || "Unknown customer";
        const company = approval.lead.company?.trim();
        const email = approval.lead.email?.trim();
        const agentName = approval.sales_run?.agent_name?.trim();
        const needsReview = approval.needs_approval;

        return (
          <li key={approval.draft_id}>
            <button
              type="button"
              className={cn(
                "hover:bg-surface-subtle focus-visible:ring-ring/40 motion-safe:transition-colors w-full p-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-inset",
                isSelected && "bg-surface-subtle",
                needsReview && "border-l-warning border-l-2",
              )}
              aria-pressed={isSelected}
              aria-current={isSelected ? "true" : undefined}
              onClick={() => onSelect?.(approval)}
            >
              <span className="flex items-start justify-between gap-3">
                <span className="min-w-0">
                  <span className="text-foreground block truncate text-sm font-semibold tracking-tight">
                    {customerName}
                  </span>
                  <span className="text-muted-foreground mt-0.5 flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs">
                    {company ? (
                      <span className="truncate">{company}</span>
                    ) : null}
                    {company && email ? (
                      <span aria-hidden="true">·</span>
                    ) : null}
                    {email ? <span className="truncate">{email}</span> : null}
                    {!company && !email ? (
                      <span className="italic">No company on file</span>
                    ) : null}
                  </span>
                </span>
                <RelativeTime
                  value={approval.updated_at}
                  className="text-muted-foreground shrink-0 text-xs"
                />
              </span>
              <span className="text-muted-foreground mt-2.5 line-clamp-2 block text-sm leading-5">
                {previewText(approval.draft.response)}
              </span>
              <span className="mt-3 flex flex-wrap items-center gap-2">
                <StatusBadge status={status.status} label={status.label} />
                {agentName ? (
                  <span className="text-muted-foreground text-xs">
                    {agentName}
                  </span>
                ) : null}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
