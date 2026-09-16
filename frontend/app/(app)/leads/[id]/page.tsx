"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { formatTimestamp } from "@/components/agents/execution-status";
import { DetailRow } from "@/components/data-display/detail-row";
import { StatePanel } from "@/components/data-display/state-panel";
import { EmptyState } from "@/components/empty-state";
import { DraftLeadResponseDialog } from "@/components/leads/draft-lead-response-dialog";
import { LeadFollowUpsDialog } from "@/components/leads/lead-follow-ups-dialog";
import { LeadFormDialog } from "@/components/leads/lead-form-dialog";
import { LeadSalesAgentHistory } from "@/components/leads/lead-sales-agent-history";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { SalesAgentStatus } from "@/components/leads/sales-agent-status";
import { StartLeadSalesRunDialog } from "@/components/leads/start-lead-sales-run-dialog";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getAgents } from "@/lib/api/agents";
import { ApiError } from "@/lib/api/client";
import { getLead } from "@/lib/api/leads";
import { getSalesRun } from "@/lib/api/sales-runs";
import type { Agent, Lead, LeadSource, SalesRun } from "@/types/api";

const statusLabels: Record<Lead["status"], string> = {
  NEW: "New",
  CONTACTED: "Contacted",
  QUALIFIED: "Qualified",
  UNQUALIFIED: "Unqualified",
  CONVERTED: "Converted",
};

const sourceLabels: Record<LeadSource, string> = {
  MANUAL: "Manual",
  WEBSITE: "Website",
  EMAIL: "Email",
  CHAT: "Chat",
  API: "API",
  IMPORT: "Import",
};

const stageLabels: Record<SalesRun["stage"], string> = {
  MATCH_LEAD: "Match lead",
  QUALIFY: "Qualify",
  DRAFT: "Draft",
  AWAIT_APPROVAL: "Await approval",
  SEND: "Send",
  DONE: "Done",
};

function isEligibleSalesAgent(agent: Agent) {
  return (
    agent.agent_type === "SALES" &&
    (agent.status === "READY" || agent.status === "ACTIVE")
  );
}

function hasOpenSalesRun(lead: Lead | null) {
  const status = lead?.latest_sales_run?.status;
  return status === "RUNNING" || status === "WAITING_APPROVAL";
}

function canReviewDraft(run: SalesRun | null) {
  if (!run?.response_draft_id) return false;
  if (run.status === "WAITING_APPROVAL") return true;
  return run.status === "FAILED" && run.stage === "SEND";
}

export default function LeadWorkspacePage() {
  const params = useParams<{ id: string }>();
  const leadId = params.id;
  const [lead, setLead] = useState<Lead | null>(null);
  const [latestRun, setLatestRun] = useState<SalesRun | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorKind, setErrorKind] = useState<"not-found" | "error" | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [startOpen, setStartOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editKey, setEditKey] = useState(0);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyKey, setHistoryKey] = useState(0);
  const [followUpsOpen, setFollowUpsOpen] = useState(false);
  const [followUpsKey, setFollowUpsKey] = useState(0);
  const [reviewOpen, setReviewOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([getLead(leadId), getAgents({ agentType: "SALES" })])
      .then(async ([data, listed]) => {
        if (cancelled) return;
        setLead(data);
        setAgents(listed);
        setErrorKind(null);
        if (data.latest_sales_run) {
          try {
            const run = await getSalesRun(
              data.latest_sales_run.agent_id,
              data.latest_sales_run.id,
            );
            if (!cancelled) setLatestRun(run);
          } catch {
            if (!cancelled) setLatestRun(null);
          }
        } else if (!cancelled) {
          setLatestRun(null);
        }
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setLead(null);
        setLatestRun(null);
        setErrorKind(
          cause instanceof ApiError && cause.status === 404 ? "not-found" : "error",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [leadId, retryKey]);

  function reload() {
    setLoading(true);
    setErrorKind(null);
    setRetryKey((value) => value + 1);
  }

  const eligibleAgents = agents.filter(isEligibleSalesAgent);
  const agentName =
    agents.find((agent) => agent.id === lead?.latest_sales_run?.agent_id)?.name ??
    null;

  if (loading) {
    return (
      <div className="gap-section flex flex-col">
        <PageHeader
          breadcrumbs={[{ label: "Leads", href: "/leads" }, { label: "Lead" }]}
          title="Lead"
        />
        <div role="status">
          <Skeleton className="h-40 w-full" />
          <span className="sr-only">Loading lead</span>
        </div>
      </div>
    );
  }

  if (!lead) {
    const notFound = errorKind === "not-found";
    return (
      <div className="gap-section flex flex-col">
        <PageHeader
          breadcrumbs={[
            { label: "Leads", href: "/leads" },
            { label: notFound ? "Lead not found" : "Lead unavailable" },
          ]}
          title={notFound ? "Lead not found" : "Lead unavailable"}
        />
        <StatePanel
          kind="error"
          className="max-w-none"
          title={notFound ? "This lead could not be found." : "This lead could not be loaded."}
          description={
            notFound
              ? "Return to Leads to select an available record."
              : "Check your connection and try again."
          }
          action={
            <div className="flex flex-wrap gap-2">
              {!notFound ? (
                <Button type="button" onClick={reload}>
                  Retry
                </Button>
              ) : null}
              <Link href="/leads" className={buttonVariants({ variant: "outline" })}>
                Back to Leads
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  const summary = lead.latest_sales_run;
  const openRun = hasOpenSalesRun(lead);

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        breadcrumbs={[{ label: "Leads", href: "/leads" }, { label: lead.name }]}
        title={lead.name}
        description={`${lead.email || "No email"} · ${statusLabels[lead.status]} · ${sourceLabels[lead.source]} · Updated ${formatTimestamp(lead.updated_at) ?? "unavailable"}`}
        secondaryActions={
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setEditKey((value) => value + 1);
              setEditOpen(true);
            }}
          >
            Edit
          </Button>
        }
        primaryAction={
          <Button
            type="button"
            disabled={openRun}
            onClick={() => setStartOpen(true)}
          >
            Start Sales Agent
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card as="section">
          <CardContent className="grid gap-4">
            <h2 className="text-section-title font-semibold tracking-tight">
              Lead
            </h2>
            <dl className="grid gap-3">
              <DetailRow label="Email" value={lead.email || "—"} muted={!lead.email} />
              <DetailRow label="Status" value={<LeadStatusBadge status={lead.status} />} />
              <DetailRow label="Source" value={sourceLabels[lead.source]} />
              <DetailRow
                label="Company"
                value={lead.company || "—"}
                muted={!lead.company}
              />
              <DetailRow
                label="Updated"
                value={formatTimestamp(lead.updated_at) ?? "—"}
              />
              <DetailRow
                label="Enquiry"
                value={
                  lead.enquiry?.trim() ? (
                    <span className="line-clamp-4 whitespace-pre-wrap">
                      {lead.enquiry}
                    </span>
                  ) : (
                    "—"
                  )
                }
                muted={!lead.enquiry?.trim()}
              />
            </dl>
          </CardContent>
        </Card>

        <section className="grid gap-4" aria-label="Sales Agent">
          <SectionHeader title="Sales Agent" />
          {!summary ? (
            eligibleAgents.length === 0 ? (
              <StatePanel
                kind="unavailable"
                className="max-w-none"
                title="No Sales Agent is ready"
                description="No Sales Agent is ready. Open AI Agents to finish setup."
                action={
                  <Link href="/agents" className={buttonVariants({ variant: "outline" })}>
                    Open AI Agents
                  </Link>
                }
              />
            ) : (
              <EmptyState
                className="max-w-none"
                title="No Sales Agent work yet"
                description="Start a run to qualify an enquiry and draft a reply. Approval does not send the email."
                action={
                  <Button type="button" onClick={() => setStartOpen(true)}>
                    Start Sales Agent
                  </Button>
                }
              />
            )
          ) : (
            <Card>
              <CardContent className="grid gap-4">
                <SalesAgentStatus summary={summary} />
                <dl className="grid gap-3">
                  <DetailRow label="Stage" value={stageLabels[summary.stage]} />
                  {agentName ? <DetailRow label="Agent" value={agentName} /> : null}
                  <DetailRow
                    label="Updated"
                    value={
                      formatTimestamp(latestRun?.updated_at ?? lead.updated_at) ??
                      "—"
                    }
                  />
                  {summary.email_send?.status === "SENT" ? (
                    <DetailRow
                      label="Email"
                      value={
                        summary.email_send.completed_at
                          ? `Sent ${formatTimestamp(summary.email_send.completed_at) ?? ""}`.trim()
                          : "Sent"
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
                <div className="flex flex-wrap gap-2">
                  {canReviewDraft(latestRun) ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setReviewOpen(true)}
                    >
                      Review draft
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setHistoryKey((value) => value + 1);
                      setHistoryOpen(true);
                    }}
                  >
                    Sales Agent history
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setFollowUpsKey((value) => value + 1);
                      setFollowUpsOpen(true);
                    }}
                  >
                    Follow-ups
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </section>
      </div>

      <StartLeadSalesRunDialog
        key={`${startOpen}-${lead.id}-${lead.enquiry ?? ""}`}
        open={startOpen}
        lead={lead}
        onOpenChange={setStartOpen}
        onCompleted={() => {
          setHistoryKey((value) => value + 1);
          reload();
        }}
      />
      <LeadFormDialog
        key={editKey}
        open={editOpen}
        lead={lead}
        onOpenChange={setEditOpen}
        onSaved={(saved) => {
          setLead(saved);
          setEditOpen(false);
        }}
      />
      <LeadSalesAgentHistory
        key={historyKey}
        open={historyOpen}
        lead={lead}
        onOpenChange={setHistoryOpen}
      />
      <LeadFollowUpsDialog
        key={followUpsKey}
        open={followUpsOpen}
        lead={lead}
        onOpenChange={setFollowUpsOpen}
      />
      <DraftLeadResponseDialog
        open={reviewOpen}
        lead={lead}
        draftId={latestRun?.response_draft_id}
        onOpenChange={setReviewOpen}
        onCompleted={() => {
          reload();
        }}
      />
    </div>
  );
}
