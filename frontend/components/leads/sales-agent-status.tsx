import { AiBadge } from "@/components/ai/ai-badge";
import { SalesRunStatusBadge } from "@/components/agents/sales-run-status-badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";
import type {
  LeadLatestSalesRunSummary,
  LeadSalesAgentAutoStartStatus,
} from "@/types/api";

type SalesAgentStatusProps = {
  summary?: LeadLatestSalesRunSummary | null;
  autoStartStatus?: LeadSalesAgentAutoStartStatus | null;
};

const autoStartLabels: Record<LeadSalesAgentAutoStartStatus, string> = {
  PENDING: "Auto-start queued",
  CLAIMED: "Auto-start in progress",
  STARTED: "Auto-start started",
  SKIPPED: "Auto-start skipped",
  FAILED: "Auto-start failed",
};

export function SalesAgentStatus({
  summary,
  autoStartStatus = null,
}: SalesAgentStatusProps) {
  if (!summary) {
    if (
      autoStartStatus === "PENDING" ||
      autoStartStatus === "CLAIMED" ||
      autoStartStatus === "FAILED" ||
      autoStartStatus === "SKIPPED"
    ) {
      const tone =
        autoStartStatus === "FAILED"
          ? "failed"
          : autoStartStatus === "SKIPPED"
            ? "draft"
            : "pending";
      return (
        <div className="grid justify-items-start gap-1.5">
          {autoStartStatus === "CLAIMED" || autoStartStatus === "PENDING" ? (
            <AiBadge label="Processing" />
          ) : null}
          <StatusBadge
            status={statusPresentation(tone, autoStartLabels[autoStartStatus]).status}
            label={autoStartLabels[autoStartStatus]}
          />
        </div>
      );
    }
    return <p className="text-muted-foreground text-sm">No sales run</p>;
  }

  const emailSent = summary.email_send?.status === "SENT";
  const followUp = summary.follow_up;
  const followUpOverdue =
    followUp?.status === "PENDING" && followUp.is_overdue === true;
  const followUpPending = followUp?.status === "PENDING" && !followUp.is_overdue;

  return (
    <div className="grid justify-items-start gap-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        {summary.status === "RUNNING" ? <AiBadge label="Processing" /> : null}
        <SalesRunStatusBadge status={summary.status} />
        {summary.status === "COMPLETED" && emailSent ? (
          <span className="text-muted-foreground text-xs">Email sent</span>
        ) : null}
        {followUpOverdue ? (
          <StatusBadge
            status={statusPresentation("OVERDUE", "Follow-up overdue").status}
            label="Follow-up overdue"
          />
        ) : null}
        {followUpPending ? (
          <StatusBadge
            status={statusPresentation("PENDING", "Follow-up pending").status}
            label="Follow-up pending"
          />
        ) : null}
      </div>
    </div>
  );
}
