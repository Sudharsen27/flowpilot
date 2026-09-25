"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { EmptyState } from "@/components/empty-state";
import { Customer360Insights } from "@/components/leads/customer-360-insights";
import { Customer360Profile } from "@/components/leads/customer-360-profile";
import { Customer360Timeline } from "@/components/leads/customer-360-timeline";
import { DraftLeadResponseDialog } from "@/components/leads/draft-lead-response-dialog";
import { LeadFollowUpsDialog } from "@/components/leads/lead-follow-ups-dialog";
import { LeadFormDialog } from "@/components/leads/lead-form-dialog";
import { LeadSalesAgentHistory } from "@/components/leads/lead-sales-agent-history";
import { StartLeadSalesRunDialog } from "@/components/leads/start-lead-sales-run-dialog";
import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getAgents } from "@/lib/api/agents";
import { ApiError } from "@/lib/api/client";
import { getInboxConversation } from "@/lib/api/inbox";
import { getLead, getLeadQualification } from "@/lib/api/leads";
import { getSalesRun } from "@/lib/api/sales-runs";
import { inboxSourceLabels } from "@/lib/inbox-labels";
import type {
  Agent,
  InboxConversationResponse,
  Lead,
  LeadQualificationResult,
  SalesRun,
} from "@/types/api";

const statusLabels: Record<Lead["status"], string> = {
  NEW: "New",
  CONTACTED: "Contacted",
  QUALIFIED: "Qualified",
  UNQUALIFIED: "Unqualified",
  CONVERTED: "Converted",
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
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const [lead, setLead] = useState<Lead | null>(null);
  const [latestRun, setLatestRun] = useState<SalesRun | null>(null);
  const [qualificationDetail, setQualificationDetail] =
    useState<LeadQualificationResult | null>(null);
  const [conversation, setConversation] =
    useState<InboxConversationResponse | null>(null);
  const [conversationLoading, setConversationLoading] = useState(true);
  const [conversationError, setConversationError] = useState<string | null>(null);
  const [conversationRetryKey, setConversationRetryKey] = useState(0);
  const [insightsDetailLoading, setInsightsDetailLoading] = useState(false);
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

        const qualificationId = data.latest_qualification?.id;
        const salesSummary = data.latest_sales_run;
        const needsDetail = Boolean(qualificationId || salesSummary);

        if (!needsDetail) {
          setLatestRun(null);
          setQualificationDetail(null);
          setInsightsDetailLoading(false);
          return;
        }

        setInsightsDetailLoading(true);
        const [runResult, qualificationResult] = await Promise.allSettled([
          salesSummary
            ? getSalesRun(salesSummary.agent_id, salesSummary.id)
            : Promise.resolve(null),
          qualificationId
            ? getLeadQualification(data.id, qualificationId)
            : Promise.resolve(null),
        ]);

        if (cancelled) return;

        setLatestRun(
          runResult.status === "fulfilled" ? runResult.value : null,
        );
        setQualificationDetail(
          qualificationResult.status === "fulfilled"
            ? qualificationResult.value
            : null,
        );
        setInsightsDetailLoading(false);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setLead(null);
        setLatestRun(null);
        setQualificationDetail(null);
        setInsightsDetailLoading(false);
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

  useEffect(() => {
    if (!leadId || loading || errorKind) {
      return;
    }

    let cancelled = false;

    void getInboxConversation(leadId)
      .then((data) => {
        if (cancelled) return;
        setConversation(data);
        setConversationError(null);
      })
      .catch(() => {
        if (cancelled) return;
        setConversation(null);
        setConversationError(
          "Conversation history could not be loaded right now.",
        );
      })
      .finally(() => {
        if (!cancelled) setConversationLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [leadId, loading, errorKind, retryKey, conversationRetryKey]);

  function reload() {
    setLoading(true);
    setConversationLoading(true);
    setConversationError(null);
    setInsightsDetailLoading(false);
    setErrorKind(null);
    setRetryKey((value) => value + 1);
  }

  function retryConversation() {
    setConversationLoading(true);
    setConversationError(null);
    setConversationRetryKey((value) => value + 1);
  }

  const eligibleAgents = agents.filter(isEligibleSalesAgent);
  const agentName =
    agents.find((agent) => agent.id === lead?.latest_sales_run?.agent_id)?.name ??
    null;

  useEffect(() => {
    if (!lead || !headingRef.current) return;
    headingRef.current.focus();
  }, [lead]);

  if (loading) {
    return (
      <div className="gap-section flex flex-col">
        <div role="status" aria-live="polite" aria-label="Selected lead" className="sr-only">
          Loading lead
        </div>
        <PageHeader
          breadcrumbs={[{ label: "Leads", href: "/leads" }, { label: "Lead" }]}
          title="Lead"
        />
        <div
          className="grid gap-4 xl:grid-cols-[minmax(16rem,20rem)_minmax(0,1fr)_minmax(16rem,20rem)]"
          role="status"
        >
          <Skeleton className="h-72 w-full" />
          <Skeleton className="order-3 h-[28rem] w-full xl:order-none" />
          <Skeleton className="order-2 h-72 w-full xl:order-none" />
        </div>
      </div>
    );
  }

  if (!lead) {
    const notFound = errorKind === "not-found";
    return (
      <div className="gap-section flex flex-col">
        <div role="status" aria-live="polite" aria-label="Selected lead" className="sr-only">
          {notFound ? "Lead not found" : "Lead unavailable"}
        </div>
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
          title={
            notFound
              ? "This lead could not be found."
              : "Unable to load customer"
          }
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

  const salesAgentActions = (
    <>
      {canReviewDraft(latestRun) ? (
        <Button type="button" variant="outline" onClick={() => setReviewOpen(true)}>
          Review draft
        </Button>
      ) : null}
      {summary ? (
        <>
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
        </>
      ) : null}
    </>
  );

  const insightsEmptyState =
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
        title="No Sales Agent activity yet"
        description="Start a run to qualify an enquiry and draft a reply. Approval does not send the email."
        action={
          <Button type="button" onClick={() => setStartOpen(true)}>
            Start Sales Agent
          </Button>
        }
      />
    );

  return (
    <div className="gap-section flex flex-col">
      <div role="status" aria-live="polite" aria-label="Selected lead" className="sr-only">
        {`Selected lead: ${lead.name}`}
      </div>
      <PageHeader
        breadcrumbs={[{ label: "Leads", href: "/leads" }, { label: lead.name }]}
        title={lead.name}
        description={`${lead.email || "No email"} · ${statusLabels[lead.status]} · ${inboxSourceLabels[lead.source]}`}
        secondaryActions={
          <div className="flex flex-wrap gap-2">
            <Link
              href="/leads"
              className={buttonVariants({ variant: "outline" })}
            >
              Back to Leads
            </Link>
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
          </div>
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

      {/* Mobile: Profile → Insights → Timeline. Desktop xl: Profile | Timeline | Insights */}
      <div className="grid gap-4 lg:gap-5 xl:grid-cols-[minmax(16rem,20rem)_minmax(0,1fr)_minmax(16rem,20rem)] xl:items-start">
        <div className="order-1 min-w-0 xl:order-none">
          <Customer360Profile
            lead={lead}
            conversationState={conversation?.lead.conversation_state}
          />
        </div>

        <div className="order-3 min-w-0 xl:order-none">
          <Customer360Timeline
            items={conversation?.items}
            totalItems={conversation?.total_items}
            loading={conversationLoading}
            error={conversationError}
            onRetry={retryConversation}
          />
        </div>

        <div className="order-2 min-w-0 xl:order-none">
          <Customer360Insights
            lead={lead}
            latestRun={latestRun}
            qualificationDetail={qualificationDetail}
            conversation={conversation}
            agentName={agentName}
            detailLoading={insightsDetailLoading}
            emptyState={insightsEmptyState}
            actions={
              summary || canReviewDraft(latestRun) ? salesAgentActions : null
            }
          />
        </div>
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
        key={`lead-edit-${editKey}`}
        open={editOpen}
        lead={lead}
        onOpenChange={setEditOpen}
        onSaved={(saved) => {
          setLead(saved);
          setEditOpen(false);
        }}
      />
      <LeadSalesAgentHistory
        key={`lead-history-${historyKey}`}
        open={historyOpen}
        lead={lead}
        onOpenChange={setHistoryOpen}
      />
      <LeadFollowUpsDialog
        key={`lead-follow-ups-${followUpsKey}`}
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
