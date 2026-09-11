import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/api/client";
import { statusPresentation } from "@/lib/status";
import type {
  AgentExecutionStatus,
  ExecutionFailureCategory,
  ToolInvocationStatus,
} from "@/types/api";

const executionLabels: Record<AgentExecutionStatus, string> = {
  QUEUED: "Queued",
  RUNNING: "Running",
  COMPLETED: "Completed",
  FAILED: "Failed",
  CANCELLED: "Cancelled",
};

const invocationLabels: Record<ToolInvocationStatus, string> = {
  SUCCESS: "Success",
  FAILED: "Failed",
  REJECTED: "Rejected",
  AWAITING_APPROVAL: "Awaiting approval",
};

export function ExecutionStatusBadge({
  status,
}: {
  status: AgentExecutionStatus;
}) {
  const presentation = statusPresentation(status, executionLabels[status]);
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}

export function ToolInvocationStatusBadge({
  status,
}: {
  status: ToolInvocationStatus;
}) {
  const presentation = statusPresentation(
    status,
    invocationLabels[status],
    status === "SUCCESS" ? "success" : "draft",
  );
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}

export function formatTimestamp(value: string | null) {
  if (!value) return null;
  return value.replace("T", " ").replace(/\.\d+Z$/, " UTC").replace(/Z$/, " UTC");
}

export function formatDuration(ms: number | null | undefined) {
  if (typeof ms !== "number" || !Number.isFinite(ms) || ms < 0) {
    return null;
  }
  if (ms < 1000) {
    return `${Math.round(ms)}ms`;
  }
  const seconds = ms / 1000;
  const formatted = seconds >= 10 ? seconds.toFixed(0) : seconds.toFixed(1);
  return `${formatted.replace(/\.0$/, "")}s`;
}

const failureCategoryLabels: Record<ExecutionFailureCategory, string> = {
  PROVIDER_ERROR: "Provider error",
  TOOL_ERROR: "Tool error",
  POLICY_ERROR: "Policy error",
  VALIDATION_ERROR: "Validation error",
  EXECUTION_ERROR: "Execution error",
  CONFIGURATION_ERROR: "Configuration error",
};

export function formatFailureCategory(
  category: ExecutionFailureCategory | null | undefined,
) {
  if (!category) return null;
  return failureCategoryLabels[category] ?? null;
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
