import Link from "next/link";
import { CheckCircle2, CircleAlert, ShieldAlert, XCircle } from "lucide-react";

import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import { buttonVariants } from "@/components/ui/button";
import { buildApprovalsHref } from "@/lib/approvals-url";
import { cn } from "@/lib/utils";
import type { OrchestrationOutcome, OrchestrationResult } from "@/types/api";

const OUTCOME_COPY: Record<
  OrchestrationOutcome,
  { title: string; description: string; status: StatusValue }
> = {
  SUCCESS: {
    title: "Execution completed",
    description: "The agent finished the requested workflow.",
    status: "success",
  },
  APPROVAL_REQUIRED: {
    title: "Human approval required",
    description:
      "The agent stopped before the protected action. No approval was performed automatically.",
    status: "warning",
  },
  TOOL_DENIED: {
    title: "Tool denied by policy",
    description:
      "A requested tool was not permitted for this organization membership.",
    status: "failed",
  },
  TOOL_FAILED: {
    title: "A tool step failed",
    description: "The agent stopped after a tool error.",
    status: "failed",
  },
  PLANNING_FAILED: {
    title: "Agent planning failed",
    description: "The agent could not produce a valid plan for this instruction.",
    status: "failed",
  },
  PLAN_VALIDATION_FAILED: {
    title: "Plan validation failed",
    description: "The generated plan could not be accepted for execution.",
    status: "failed",
  },
  EXECUTION_FAILED: {
    title: "Execution failed",
    description: "The agent could not complete this run.",
    status: "failed",
  },
};

function formatToolName(name: string) {
  return name.replaceAll("_", " ");
}

function stepStatusLabel(result: OrchestrationResult["step_results"][number]) {
  if (!result.result) return "Not executed";
  if (result.result.success) return "Completed";
  if (result.result.outcome === "APPROVAL_REQUIRED") {
    return "Approval required";
  }
  if (result.result.outcome === "PERMISSION_DENIED") return "Denied";
  if (result.result.outcome === "VALIDATION_FAILURE") return "Invalid";
  return "Failed";
}

function stoppedAtLabel(result: OrchestrationResult): string | null {
  if (!result.stopped_at_step_id) return null;
  const step = result.step_results.find(
    (item) => item.step_id === result.stopped_at_step_id,
  );
  if (step) return formatToolName(step.tool_name);
  return result.stopped_at_step_id;
}

/**
 * Resolve Approval Center href from orchestration payload only.
 * Never invents a draft/approval id. Specific selection requires an explicit
 * server-provided draft id (not available on current OrchestrationResult).
 */
export function approvalHandoffHref(
  result: Pick<OrchestrationResult, "approval_required">,
): string | null {
  if (!result.approval_required) return null;
  return buildApprovalsHref();
}

type AgentWorkspaceResultProps = {
  result: OrchestrationResult;
};

export function AgentWorkspaceResult({ result }: AgentWorkspaceResultProps) {
  const copy = OUTCOME_COPY[result.outcome];
  const Icon =
    result.outcome === "SUCCESS"
      ? CheckCircle2
      : result.outcome === "APPROVAL_REQUIRED"
        ? ShieldAlert
        : result.outcome === "TOOL_DENIED"
          ? ShieldAlert
          : result.outcome === "PLANNING_FAILED" ||
              result.outcome === "PLAN_VALIDATION_FAILED"
            ? CircleAlert
            : XCircle;
  const stoppedAt = stoppedAtLabel(result);
  const approvalsHref = approvalHandoffHref(result);

  return (
    <section
      aria-labelledby="agent-workspace-result-title"
      className="border-border bg-card shadow-card rounded-xl border p-5 sm:p-6"
      data-slot="agent-workspace-result"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
            Agent result
          </p>
          <h2
            id="agent-workspace-result-title"
            className="mt-1 flex items-center gap-2 text-base font-semibold tracking-tight"
          >
            <Icon className="size-4 shrink-0" aria-hidden="true" />
            {copy.title}
          </h2>
          <p className="text-muted-foreground mt-1.5 text-sm leading-6">
            {copy.description}
          </p>
        </div>
        <StatusBadge status={copy.status} label={result.outcome.replaceAll("_", " ")} />
      </div>

      <dl className="border-border mt-5 grid gap-3 border-t pt-4 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground text-xs font-medium">Execution</dt>
          <dd className="mt-1 font-mono text-xs break-all">
            {result.execution_id ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground text-xs font-medium">Steps</dt>
          <dd className="mt-1 font-medium">
            {result.completed_step_count} / {result.total_step_count} completed
          </dd>
        </div>
        {result.approval_required ? (
          <div>
            <dt className="text-muted-foreground text-xs font-medium">Status</dt>
            <dd className="mt-1 font-medium">Approval required</dd>
          </div>
        ) : result.execution_status ? (
          <div>
            <dt className="text-muted-foreground text-xs font-medium">
              Execution status
            </dt>
            <dd className="mt-1 font-medium">{result.execution_status}</dd>
          </div>
        ) : null}
        {stoppedAt ? (
          <div>
            <dt className="text-muted-foreground text-xs font-medium">
              Stopped at
            </dt>
            <dd className="mt-1 font-medium capitalize">{stoppedAt}</dd>
          </div>
        ) : null}
      </dl>

      {result.error ? (
        <p className="text-danger-text mt-4 text-sm" role="alert">
          {result.error}
        </p>
      ) : null}

      {approvalsHref ? (
        <div
          className="border-warning/30 bg-warning/10 mt-4 rounded-md border px-3 py-3"
          role="status"
        >
          <Link
            href={approvalsHref}
            className={cn(
              buttonVariants({ variant: "outline", size: "sm" }),
              "border-warning/40 bg-background text-foreground hover:bg-background/90",
            )}
          >
            Review in Approvals
          </Link>
        </div>
      ) : null}

      {result.step_results.length > 0 ? (
        <ol className="border-border mt-5 space-y-3 border-t pt-4">
          {result.step_results.map((step, index) => {
            const ok = Boolean(step.result?.success);
            return (
              <li
                key={step.step_id}
                className="flex items-start gap-3 text-sm"
              >
                <span
                  className={
                    ok
                      ? "text-success-text mt-0.5"
                      : "text-muted-foreground mt-0.5"
                  }
                  aria-hidden="true"
                >
                  {ok ? "✓" : `${index + 1}.`}
                </span>
                <div className="min-w-0">
                  <p className="font-medium capitalize">
                    {formatToolName(step.tool_name)}
                  </p>
                  <p className="text-muted-foreground mt-0.5 text-xs">
                    {stepStatusLabel(step)}
                    {step.result?.error ? ` — ${step.result.error}` : null}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      ) : null}
    </section>
  );
}
