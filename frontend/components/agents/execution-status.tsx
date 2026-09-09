import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/api/client";
import type { AgentExecutionStatus, ToolInvocationStatus } from "@/types/api";

const executionPresentation: Record<
  AgentExecutionStatus,
  { status: StatusValue; label: string }
> = {
  QUEUED: { status: "pending", label: "Queued" },
  RUNNING: { status: "pending", label: "Running" },
  COMPLETED: { status: "success", label: "Completed" },
  FAILED: { status: "failed", label: "Failed" },
};

const invocationPresentation: Record<
  ToolInvocationStatus,
  { status: StatusValue; label: string }
> = {
  SUCCESS: { status: "success", label: "Success" },
  FAILED: { status: "failed", label: "Failed" },
  REJECTED: { status: "warning", label: "Rejected" },
  AWAITING_APPROVAL: { status: "pending", label: "Awaiting approval" },
};

export function ExecutionStatusBadge({
  status,
}: {
  status: AgentExecutionStatus;
}) {
  const presentation = executionPresentation[status];
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}

export function ToolInvocationStatusBadge({
  status,
}: {
  status: ToolInvocationStatus;
}) {
  const presentation = invocationPresentation[status];
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}

export function formatTimestamp(value: string | null) {
  if (!value) return null;
  return value.replace("T", " ").replace(/\.\d+Z$/, " UTC").replace(/Z$/, " UTC");
}

export function historyErrorMessage(
  cause: unknown,
  fallback: string,
  notFound: string,
) {
  if (cause instanceof ApiError) {
    if (cause.status === 401) {
      return "Your session has expired. Sign in again to view this history.";
    }
    if (cause.status === 403) {
      return "You do not have permission to view this history.";
    }
    if (cause.status === 404) {
      return notFound;
    }
  }
  return fallback;
}
