import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";
import type {
  LeadFollowUp,
  LeadFollowUpExecutionStatus,
  LeadFollowUpStatus,
  LeadFollowUpType,
} from "@/types/api";

const followUpLabels: Record<LeadFollowUpStatus, string> = {
  PENDING: "Pending",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

const executionLabels: Record<LeadFollowUpExecutionStatus, string> = {
  PENDING: "Queued",
  RUNNING: "Sending",
  SENT: "Sent",
  FAILED: "Failed",
};

const typeLabels: Record<LeadFollowUpType, string> = {
  EMAIL_FOLLOW_UP: "Email",
  MANUAL_FOLLOW_UP: "Manual",
};

/**
 * Follow-up lifecycle state. A pending follow-up that is past due reads as
 * "Overdue" so operators can triage it, but its underlying status is unchanged.
 */
export function FollowUpStatusBadge({ followUp }: { followUp: LeadFollowUp }) {
  if (followUp.status === "PENDING" && followUp.is_overdue) {
    const presentation = statusPresentation("OVERDUE", "Overdue");
    return (
      <StatusBadge status={presentation.status} label={presentation.label} />
    );
  }
  const presentation = statusPresentation(
    followUp.status,
    followUpLabels[followUp.status],
  );
  return <StatusBadge status={presentation.status} label={presentation.label} />;
}

/**
 * Delivery state of the latest attempt. Never implies an email was sent
 * unless the backend execution actually reached SENT.
 */
export function FollowUpExecutionStatusBadge({
  status,
}: {
  status: LeadFollowUpExecutionStatus;
}) {
  const presentation = statusPresentation(status, executionLabels[status]);
  return <StatusBadge status={presentation.status} label={presentation.label} />;
}

export function followUpTypeLabel(type: LeadFollowUpType) {
  return typeLabels[type];
}
