import type { ReactNode } from "react";
import { Bot, Sparkles } from "lucide-react";

import { AiBadge } from "@/components/ai/ai-badge";
import { DetailRow } from "@/components/data-display/detail-row";
import { QualificationStatus } from "@/components/leads/qualification-status";
import { SalesAgentStatus } from "@/components/leads/sales-agent-status";
import { RelativeTime } from "@/components/ui/relative-time";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { draftReviewLabels } from "@/lib/inbox-labels";
import type {
  Lead,
  LeadLatestSalesRunSummary,
  LeadQualificationResult,
  SalesRun,
} from "@/types/api";

type Customer360InsightsProps = {
  lead: Lead;
  latestRun?: SalesRun | null;
  qualificationDetail?: LeadQualificationResult | null;
  agentName?: string | null;
  loading?: boolean;
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

function confidenceLabel(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return null;
  }
  return `${Math.round(value * 100)}% confidence`;
}

export function Customer360Insights({
  lead,
  latestRun = null,
  qualificationDetail = null,
  agentName = null,
  loading = false,
  emptyState,
  actions,
}: Customer360InsightsProps) {
  const summary = lead.latest_sales_run;
  const qualification = lead.latest_qualification;
  const draft = lead.latest_response_draft;
  const analysis = qualificationDetail?.analysis;

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

  const hasAnyInsight = Boolean(qualification || draft || summary || analysis);

  return (
    <section
      className="bg-card border-border grid content-start gap-4 rounded-lg border p-4"
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
            From FlowPilot qualification, drafts, and Sales Agent runs.
          </p>
        </div>
      </div>

      {!hasAnyInsight
        ? (emptyState ?? (
            <p className="text-muted-foreground text-sm leading-6">
              No AI activity yet. Start a Sales Agent run to qualify the enquiry
              and prepare a draft for human review.
            </p>
          ))
        : null}

      {qualification || analysis ? (
        <div className="border-ai-border bg-ai/5 rounded-md border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">Qualification</span>
          </div>
          <div className="mt-2">
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
          </div>
          {analysis?.summary ? (
            <p className="text-muted-foreground mt-2 text-xs leading-5">
              {analysis.summary}
            </p>
          ) : null}
          {analysis?.intent ? (
            <p className="text-muted-foreground mt-1 text-xs">
              Intent: {analysis.intent.replaceAll("_", " ").toLowerCase()}
            </p>
          ) : null}
          {analysis?.buying_signals?.length ? (
            <ul className="text-muted-foreground mt-2 list-inside list-disc text-xs leading-5">
              {analysis.buying_signals.slice(0, 3).map((signal) => (
                <li key={signal}>{signal}</li>
              ))}
            </ul>
          ) : null}
          {qualification?.created_at ? (
            <RelativeTime
              value={qualification.created_at}
              className="mt-2 block"
            />
          ) : null}
        </div>
      ) : null}

      {draft ? (
        <div className="border-ai-border bg-ai/5 rounded-md border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <AiBadge label="Generated" />
            <span className="text-sm font-medium">Latest AI draft</span>
          </div>
          <p className="text-ai-text mt-2 text-xs font-medium">
            Prepared by FlowPilot AI · Not sent until approved
          </p>
          <dl className="mt-2 grid gap-2">
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
                    label={draftReviewLabels[draft.review_status]}
                  />
                ) : (
                  draft.status
                )
              }
            />
            <DetailRow
              label="Created"
              value={<RelativeTime value={draft.created_at} className="text-sm" />}
            />
          </dl>
        </div>
      ) : null}

      {summary ? (
        <div className="border-border rounded-md border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Bot className="text-muted-foreground size-4" aria-hidden="true" />
            <span className="text-sm font-medium">Sales Agent</span>
          </div>
          <div className="mt-2">
            <SalesAgentStatus summary={summary} />
          </div>
          <dl className="mt-3 grid gap-2">
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
              <DetailRow label="Email" value="Send failed" />
            ) : null}
            {summary.follow_up ? (
              <DetailRow
                label="Follow-up"
                value={
                  summary.follow_up.is_overdue
                    ? "Overdue"
                    : summary.follow_up.status === "PENDING"
                      ? "Pending"
                      : summary.follow_up.status === "COMPLETED"
                        ? "Completed"
                        : "Cancelled"
                }
              />
            ) : null}
          </dl>
        </div>
      ) : null}

      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </section>
  );
}
