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

export type CreatedDraftSummary = {
  draftId: string;
  leadId: string | null;
  status: string | null;
  reviewStatus: string | null;
  revision: number | null;
};

export type ApprovalHandoff = {
  href: string;
  label: "Review draft" | "Review in Approvals";
  draft: CreatedDraftSummary | null;
};

function formatToolName(name: string) {
  return name.replaceAll("_", " ");
}

function asNonEmptyString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function asOptionalNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Extract a real draft created by create_response_draft tool output only.
 * Never uses execution_id or planner arguments.
 */
export function extractCreatedDraft(
  result: Pick<OrchestrationResult, "step_results">,
): CreatedDraftSummary | null {
  let found: CreatedDraftSummary | null = null;
  for (const step of result.step_results) {
    if (step.tool_name !== "create_response_draft") continue;
    const toolResult = step.result;
    if (!toolResult?.success || !toolResult.output) continue;
    const draftId = asNonEmptyString(toolResult.output.draft_id);
    if (!draftId) continue;
    found = {
      draftId,
      leadId: asNonEmptyString(toolResult.output.lead_id),
      status: asNonEmptyString(toolResult.output.status),
      reviewStatus: asNonEmptyString(toolResult.output.review_status),
      revision: asOptionalNumber(toolResult.output.revision),
    };
  }
  return found;
}

/**
 * Resolve Approval Center handoff from orchestration payload only.
 * Prefers exact draft deep-link when create_response_draft returned draft_id.
 * Falls back to Approvals root only when approval_required and no draft_id.
 */
export function resolveApprovalHandoff(
  result: Pick<
    OrchestrationResult,
    "approval_required" | "step_results" | "execution_id"
  >,
): ApprovalHandoff | null {
  const draft = extractCreatedDraft(result);
  if (draft) {
    return {
      href: buildApprovalsHref({ approvalId: draft.draftId }),
      label: "Review draft",
      draft,
    };
  }
  if (result.approval_required) {
    return {
      href: buildApprovalsHref(),
      label: "Review in Approvals",
      draft: null,
    };
  }
  return null;
}

/** @deprecated Prefer resolveApprovalHandoff — kept for existing imports/tests. */
export function approvalHandoffHref(
  result: Pick<
    OrchestrationResult,
    "approval_required" | "step_results" | "execution_id"
  >,
): string | null {
  return resolveApprovalHandoff(result)?.href ?? null;
}

function stepStatusLabel(result: OrchestrationResult["step_results"][number]) {
  if (!result.result) return "Not executed";
  if (result.result.success) {
    if (result.tool_name === "create_response_draft") {
      return "Completed — Draft created. Review required before sending.";
    }
    return "Completed";
  }
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
  const handoff = resolveApprovalHandoff(result);
  const createdDraft = handoff?.draft ?? null;

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
        {result.approval_required && !createdDraft ? (
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

      {handoff ? (
        <div
          className={cn(
            "mt-4 rounded-md border px-3 py-3",
            createdDraft
              ? "border-warning/30 bg-warning/10"
              : "border-warning/30 bg-warning/10",
          )}
          role="status"
        >
          {createdDraft ? (
            <>
              <p className="text-sm font-medium">Draft created</p>
              <p className="text-muted-foreground mt-1 text-sm leading-6">
                Review required before sending. No approval or send was performed
                automatically.
              </p>
              <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                <div>
                  <dt className="text-muted-foreground">Draft ID</dt>
                  <dd className="mt-0.5 font-mono break-all">
                    {createdDraft.draftId}
                  </dd>
                </div>
                {createdDraft.leadId ? (
                  <div>
                    <dt className="text-muted-foreground">Lead ID</dt>
                    <dd className="mt-0.5 font-mono break-all">
                      {createdDraft.leadId}
                    </dd>
                  </div>
                ) : null}
                {createdDraft.reviewStatus ? (
                  <div>
                    <dt className="text-muted-foreground">Review status</dt>
                    <dd className="mt-0.5 font-medium">
                      {createdDraft.reviewStatus}
                    </dd>
                  </div>
                ) : null}
              </dl>
            </>
          ) : null}
          <div className={createdDraft ? "mt-3" : undefined}>
            <Link
              href={handoff.href}
              className={cn(
                buttonVariants({ variant: "outline", size: "sm" }),
                "border-warning/40 bg-background text-foreground hover:bg-background/90",
              )}
            >
              {handoff.label}
            </Link>
          </div>
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
