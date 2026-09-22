import { ClipboardCheck } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { RelativeTime } from "@/components/ui/relative-time";
import { StatusBadge } from "@/components/ui/status-badge";
import { draftReviewLabels } from "@/lib/inbox-labels";
import { statusPresentation } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { ApprovalQueueItem } from "@/types/api";

type ApprovalQueueProps = {
  approvals: ApprovalQueueItem[];
  selectedId?: string | null;
  onSelect?: (approval: ApprovalQueueItem) => void;
  emptyTitle?: string;
  emptyDescription?: string;
};

function previewText(value: string | null | undefined) {
  if (!value) return "No AI response yet";
  const cleaned = value.replace(/\s+/g, " ").trim();
  if (!cleaned) return "No AI response yet";
  return cleaned.length > 140 ? `${cleaned.slice(0, 139)}…` : cleaned;
}

export function ApprovalQueue({
  approvals,
  selectedId,
  onSelect,
  emptyTitle = "You're all caught up.",
  emptyDescription = "There are no approvals currently requiring review.",
}: ApprovalQueueProps) {
  if (approvals.length === 0) {
    return (
      <EmptyState
        compact
        icon={<ClipboardCheck />}
        className="max-w-none rounded-none border-x-0 border-b-0 shadow-none"
        title={emptyTitle}
        description={emptyDescription}
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
        const review = approval.draft.review_status;
        const reviewStatus = review
          ? statusPresentation(
              review,
              draftReviewLabels[review] ?? review,
            )
          : statusPresentation("PENDING", "Needs review");
        const isSelected = selectedId === approval.draft_id;
        const agentLabel =
          approval.sales_run?.agent_name ??
          (approval.sales_run ? "Sales Agent" : "Standalone draft");
        const runLabel =
          approval.sales_run?.status === "WAITING_APPROVAL"
            ? "Waiting for approval"
            : approval.sales_run
              ? approval.sales_run.status.replaceAll("_", " ")
              : "Standalone draft";

        return (
          <li key={approval.draft_id}>
            <button
              type="button"
              className={cn(
                "hover:bg-surface-subtle focus-visible:ring-ring/40 w-full p-4 text-left transition-colors outline-none focus-visible:ring-2 focus-visible:ring-inset",
                isSelected && "bg-surface-subtle",
              )}
              aria-pressed={isSelected}
              aria-current={isSelected ? "true" : undefined}
              onClick={() => onSelect?.(approval)}
            >
              <span className="flex items-start justify-between gap-3">
                <span className="min-w-0">
                  <span className="text-muted-foreground block text-[0.65rem] font-medium tracking-wide uppercase">
                    Needs your review
                  </span>
                  <span className="mt-1 block text-sm font-medium">
                    {approval.lead.company?.trim() || approval.lead.name}
                  </span>
                  <span className="text-muted-foreground mt-0.5 block truncate text-xs">
                    {approval.lead.email?.trim() || approval.lead.name}
                  </span>
                </span>
                <RelativeTime
                  value={approval.updated_at}
                  className="text-muted-foreground shrink-0 text-xs"
                />
              </span>
              <span className="text-muted-foreground mt-3 line-clamp-2 block text-sm leading-5">
                “{previewText(approval.draft.response)}”
              </span>
              <span className="mt-3 flex flex-wrap items-center gap-2">
                <StatusBadge
                  status={reviewStatus.status}
                  label={reviewStatus.label}
                />
                <span className="text-muted-foreground text-xs">
                  {agentLabel}
                  {approval.sales_run ? ` · ${runLabel}` : null}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
