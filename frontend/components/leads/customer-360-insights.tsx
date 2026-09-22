import type { ReactNode } from "react";
import { Bot, Sparkles } from "lucide-react";

import { AiBadge } from "@/components/ai/ai-badge";
import { DetailRow } from "@/components/data-display/detail-row";
import { QualificationStatus } from "@/components/leads/qualification-status";
import { SalesAgentStatus } from "@/components/leads/sales-agent-status";
import { RelativeTime } from "@/components/ui/relative-time";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  deriveCustomer360NextStep,
  type Customer360NextStep,
} from "@/lib/customer-360-state";
import { draftReviewLabels } from "@/lib/inbox-labels";
import { cn } from "@/lib/utils";
import type {
  InboxConversationResponse,
  Lead,
  LeadLatestSalesRunSummary,
  LeadQualificationResult,
  SalesRun,
} from "@/types/api";

type Customer360InsightsProps = {
  lead: Lead;
  latestRun?: SalesRun | null;
  qualificationDetail?: LeadQualificationResult | null;
  conversation?: InboxConversationResponse | null;
  agentName?: string | null;
  loading?: boolean;
  detailLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyState?: ReactNode;
  actions?: ReactNode;
};

const stageLabels: Record<LeadLatestSalesRunSummary["stage"], string> = {
  MATCH_LEAD: "Match lead",
  QUALIFY: "Qualify",
  DRAFT: "Draft",
  AWAIT_APPROVAL: "Await approval",
  SEND: "Send",
  DONE: "Done",
};

const intentLabels: Record<string, string> = {
  REQUEST_DEMO: "Request demo",
  REQUEST_PRICING: "Request pricing",
  GENERAL_ENQUIRY: "General enquiry",
  SUPPORT_REQUEST: "Support request",
  OTHER: "Other",
};

function confidenceLabel(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return null;
  }
  return `${Math.round(value * 100)}% confidence`;
}

function nextStepTone(kind: Customer360NextStep["kind"]) {
  switch (kind) {
    case "review":
      return "border-warning/30 bg-warning/10";
    case "failed":
      return "border-destructive/25 bg-destructive/5";
    case "follow-up":
      return "border-info/25 bg-info/5";
    case "progress":
      return "border-ai-border bg-ai/5";
    case "complete":
      return "border-success/25 bg-success/5";
    default:
      return "border-border bg-muted/40";
  }
}

export function Customer360Insights({
  lead,
  latestRun = null,
  qualificationDetail = null,
  conversation = null,
  agentName = null,
  loading = false,
  detailLoading = false,
  error = null,
  onRetry,
  emptyState,
  actions,
}: Customer360InsightsProps) {
  const summary = lead.latest_sales_run;
  const qualification = lead.latest_qualification;
  const draft = lead.latest_response_draft;
  const analysis = qualificationDetail?.analysis;
  const nextStep = deriveCustomer360NextStep(lead, conversation);

  if (loading) {
    return (
      <section
        className="bg-card border-border rounded-lg border p-4"
        aria-labelledby="customer-360-insights-title"
      >
        <h2 id="customer-360-insights-title" className="sr-only">
          AI insights
        </h2>
        <div className="grid gap-3" role="status">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-24 w-full" />
          <span className="sr-only">Loading AI insights</span>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section
        className="bg-card border-border grid content-start gap-4 rounded-lg border p-4"
        aria-labelledby="customer-360-insights-title"
      >
        <h2
          id="customer-360-insights-title"
          className="text-sm font-semibold tracking-tight"
        >
          AI insights
        </h2>
        <div
          className="border-destructive/25 bg-destructive/5 rounded-md border px-3 py-3"
          role="alert"
        >
          <p className="text-sm font-medium">AI insights are temporarily unavailable</p>
          <p className="text-muted-foreground mt-1 text-xs leading-5">{error}</p>
          {onRetry ? (
            <button
              type="button"
              className="text-foreground mt-3 text-sm font-medium underline-offset-4 hover:underline"
              onClick={onRetry}
            >
              Retry
            </button>
          ) : null}
        </div>
      </section>
    );
  }

  const hasAnyInsight = Boolean(qualification || draft || summary || analysis);

  return (
    <section
      className="bg-card border-border grid content-start gap-5 rounded-lg border p-4"
      aria-labelledby="customer-360-insights-title"
    >
      <div className="flex items-center gap-2">
        <span
          className="bg-ai/10 text-ai-text flex size-8 items-center justify-center rounded-md"
          aria-hidden="true"
        >
          <Sparkles className="size-4" />
        </span>
        <div>
          <h2
            id="customer-360-insights-title"
            className="text-sm font-semibold tracking-tight"
          >
            AI insights
          </h2>
          <p className="text-muted-foreground text-xs">
            What FlowPilot understood, prepared, and left for human review.
          </p>
        </div>
      </div>

      <div
        className={cn("rounded-md border px-3 py-3", nextStepTone(nextStep.kind))}
        role="status"
        aria-labelledby="customer-360-next-step-title"
      >
        <p className="text-muted-foreground text-[0.6875rem] font-medium tracking-wide uppercase">
          Next step
        </p>
        <p
          id="customer-360-next-step-title"
          className="mt-1 text-sm font-semibold tracking-tight"
        >
          {nextStep.title}
        </p>
        <p className="text-muted-foreground mt-1 text-xs leading-5">
          {nextStep.description}
        </p>
      </div>

      {!hasAnyInsight
        ? (emptyState ?? (
            <p className="text-muted-foreground text-sm leading-6">
              No Sales Agent activity yet. Start a run to qualify the enquiry and
              prepare a draft for human review.
            </p>
          ))
        : null}

      {hasAnyInsight && !qualification && !analysis ? (
        <p className="text-muted-foreground text-xs">No AI qualification yet.</p>
      ) : null}

      {qualification || analysis ? (
        <div className="border-ai-border/60 grid gap-2 border-l-2 pl-3">
          <div className="flex flex-wrap items-center gap-2">
            <AiBadge label="Analysis" />
            <span className="text-sm font-medium">AI qualification</span>
          </div>
          <QualificationStatus
            status={
              qualification?.status === "FAILED"
                ? "failed"
                : (qualification?.qualification ??
                  analysis?.qualification ??
                  "not-assessed")
            }
            explanation={
              qualification?.status === "FAILED"
                ? qualification.error ?? "Qualification failed."
                : confidenceLabel(
                    analysis?.confidence ?? qualification?.confidence,
                  ) ?? undefined
            }
          />
          {detailLoading && !analysis ? (
            <Skeleton className="h-12 w-full" />
          ) : null}
          {analysis?.summary ? (
            <p className="text-muted-foreground text-xs leading-5">
              {analysis.summary}
            </p>
          ) : null}
          {analysis?.intent ? (
            <p className="text-muted-foreground text-xs">
              Intent:{" "}
              {intentLabels[analysis.intent] ??
                analysis.intent.replaceAll("_", " ").toLowerCase()}
            </p>
          ) : null}
          {analysis?.buying_signals?.length ? (
            <div>
              <p className="text-muted-foreground text-[0.6875rem] font-medium tracking-wide uppercase">
                Buying signals
              </p>
              <ul className="text-muted-foreground mt-1 list-inside list-disc text-xs leading-5">
                {analysis.buying_signals.slice(0, 3).map((signal, index) => (
                  <li key={`signal-${index}-${signal}`}>{signal}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {analysis?.missing_information?.length ? (
            <div>
              <p className="text-muted-foreground text-[0.6875rem] font-medium tracking-wide uppercase">
                Missing information
              </p>
              <ul className="text-muted-foreground mt-1 list-inside list-disc text-xs leading-5">
                {analysis.missing_information.slice(0, 3).map((item, index) => (
                  <li key={`missing-${index}-${item}`}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {qualification?.created_at ? (
            <RelativeTime
              value={qualification.created_at}
              className="mt-1 block"
            />
          ) : null}
        </div>
      ) : null}

      {hasAnyInsight && !draft ? (
        <p className="text-muted-foreground text-xs">No response draft yet.</p>
      ) : null}

      {draft ? (
        <div className="border-ai-border/60 grid gap-2 border-l-2 pl-3">
          <div className="flex flex-wrap items-center gap-2">
            <AiBadge label="Generated" />
            <span className="text-sm font-medium">Latest AI draft</span>
          </div>
          <p className="text-ai-text text-xs font-medium">
            Prepared by FlowPilot AI · Not sent to the customer
          </p>
          <dl className="grid gap-2">
            <DetailRow
              label="Review"
              value={
                draft.review_status ? (
                  <StatusBadge
                    status={
                      draft.review_status === "APPROVED"
                        ? "success"
                        : draft.review_status === "REJECTED"
                          ? "failed"
                          : draft.review_status === "EDITED" ||
                              draft.review_status === "GENERATED"
                            ? "warning"
                            : "draft"
                    }
                    label={
                      draft.review_status === "GENERATED" ||
                      draft.review_status === "EDITED"
                        ? "Needs your review"
                        : draft.review_status === "REJECTED"
                          ? "Rejected"
                          : draftReviewLabels[draft.review_status]
                    }
                  />
                ) : (
                  draft.status
                )
              }
            />
            <DetailRow
              label="Created"
              value={
                <RelativeTime value={draft.created_at} className="text-sm" />
              }
            />
          </dl>
        </div>
      ) : null}

      {hasAnyInsight && !summary ? (
        <p className="text-muted-foreground text-xs">
          No Sales Agent activity yet.
        </p>
      ) : null}

      {summary ? (
        <div className="border-border/80 grid gap-2 border-l-2 pl-3">
          <div className="flex flex-wrap items-center gap-2">
            <Bot className="text-muted-foreground size-4" aria-hidden="true" />
            <span className="text-sm font-medium">Sales Agent</span>
          </div>
          <SalesAgentStatus summary={summary} />
          <dl className="grid gap-2">
            <DetailRow label="Stage" value={stageLabels[summary.stage]} />
            {agentName ? <DetailRow label="Agent" value={agentName} /> : null}
            <DetailRow
              label="Updated"
              value={
                <RelativeTime
                  value={latestRun?.updated_at ?? lead.updated_at}
                  className="text-sm"
                />
              }
            />
            {summary.email_send?.status === "SENT" ? (
              <DetailRow
                label="Email"
                value={
                  summary.email_send.completed_at ? (
                    <span>
                      Sent{" "}
                      <RelativeTime
                        value={summary.email_send.completed_at}
                        className="inline text-sm"
                      />
                    </span>
                  ) : (
                    "Sent"
                  )
                }
              />
            ) : null}
            {summary.email_send?.status === "FAILED" ? (
              <DetailRow label="Email" value="Failed" />
            ) : null}
            {summary.follow_up ? (
              <DetailRow
                label="Follow-up"
                value={
                  summary.follow_up.is_overdue
                    ? "Overdue"
                    : summary.follow_up.status === "PENDING"
                      ? "Scheduled"
                      : summary.follow_up.status === "COMPLETED"
                        ? "Completed"
                        : "Cancelled"
                }
              />
            ) : null}
          </dl>
        </div>
      ) : null}

      {actions ? (
        <div className="flex flex-wrap gap-2 border-t border-border pt-4">
          {actions}
        </div>
      ) : null}
    </section>
  );
}
