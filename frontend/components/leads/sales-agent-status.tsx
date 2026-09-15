import { AiBadge } from "@/components/ai/ai-badge";
import { SalesRunStatusBadge } from "@/components/agents/sales-run-status-badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";
import type { LeadLatestSalesRunSummary } from "@/types/api";

type SalesAgentStatusProps = {
  summary?: LeadLatestSalesRunSummary | null;
};

export function SalesAgentStatus({ summary }: SalesAgentStatusProps) {
  if (!summary) {
    return (
      <p className="text-muted-foreground text-sm">No sales run</p>
    );
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
