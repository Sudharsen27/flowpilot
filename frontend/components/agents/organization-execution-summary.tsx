import { EXECUTION_STATUS_LABELS } from "@/components/agents/execution-status";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { AGENT_EXECUTION_STATUSES } from "@/lib/agent-executions-url";
import { statusPresentation } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { AgentExecutionStatus } from "@/types/api";

export type ExecutionStatusCounts = Partial<Record<AgentExecutionStatus, number>>;

export function executionCount(
  counts: ExecutionStatusCounts | null | undefined,
  status: AgentExecutionStatus,
) {
  const value = counts?.[status];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

type OrganizationExecutionSummaryProps = {
  counts: ExecutionStatusCounts | null;
  loading?: boolean;
  activeStatus: AgentExecutionStatus | null;
  onSelectStatus: (status: AgentExecutionStatus | null) => void;
};

/**
 * Organization-wide counts per status. They come from `status_counts`, which the
 * backend never narrows by the list filters, so the labels say so explicitly.
 */
export function OrganizationExecutionSummary({
  counts,
  loading = false,
  activeStatus,
  onSelectStatus,
}: OrganizationExecutionSummaryProps) {
  return (
    <div className="grid gap-2">
      <ul
        className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5"
        aria-label="Executions by status across your organization"
      >
        {AGENT_EXECUTION_STATUSES.map((status) => {
          const label = EXECUTION_STATUS_LABELS[status];
          const count = executionCount(counts, status);
          const selected = activeStatus === status;
          const presentation = statusPresentation(status, label);
          return (
            <li key={status} className="min-w-0">
              <button
                type="button"
                aria-pressed={selected}
                aria-label={
                  loading && !counts
                    ? `${label} executions loading`
                    : `${label}: ${count} across organization${selected ? ", filter applied" : ""}`
                }
                disabled={loading && !counts}
                onClick={() => onSelectStatus(selected ? null : status)}
                className={cn(
                  "border-border bg-card shadow-card hover:bg-muted/60 focus-visible:ring-ring grid w-full gap-2 rounded-lg border p-4 text-left outline-none focus-visible:ring-2 disabled:cursor-default",
                  selected && "border-ring bg-muted/40",
                )}
              >
                <StatusBadge status={presentation.status} label={label} />
                {loading && !counts ? (
                  <Skeleton className="h-7 w-12" />
                ) : (
                  <span className="text-metric font-semibold tracking-tight tabular-nums">
                    {count}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
      <p className="text-muted-foreground text-xs leading-5">
        All-time counts across your organization. Select a status to filter the
        list; counts do not change with the agent or lead filters.
      </p>
    </div>
  );
}
