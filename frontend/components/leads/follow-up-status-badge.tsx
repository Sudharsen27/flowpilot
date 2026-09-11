import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import type {
  LeadFollowUp,
  LeadFollowUpExecutionStatus,
  LeadFollowUpStatus,
  LeadFollowUpType,
} from "@/types/api";

const followUpPresentation: Record<
  LeadFollowUpStatus,
  { status: StatusValue; label: string }
> = {
  PENDING: { status: "pending", label: "Pending" },
  COMPLETED: { status: "success", label: "Completed" },
  CANCELLED: { status: "paused", label: "Cancelled" },
};

const executionPresentation: Record<
  LeadFollowUpExecutionStatus,
  { status: StatusValue; label: string }
> = {
  PENDING: { status: "pending", label: "Queued" },
  RUNNING: { status: "pending", label: "Sending" },
  SENT: { status: "success", label: "Sent" },
  FAILED: { status: "failed", label: "Failed" },
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
    return <StatusBadge status="high" label="Overdue" />;
  }
  const presentation = followUpPresentation[followUp.status];
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
  const presentation = executionPresentation[status];
  return <StatusBadge status={presentation.status} label={presentation.label} />;
}

export function followUpTypeLabel(type: LeadFollowUpType) {
  return typeLabels[type];
}
