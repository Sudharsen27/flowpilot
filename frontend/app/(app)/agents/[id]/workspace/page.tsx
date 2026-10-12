"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AgentStatusBadge } from "@/components/agents/agent-status-badge";
import {
  AgentWorkspacePanel,
  orchestrationErrorMessage,
} from "@/components/agents/agent-workspace-panel";
import { AiBadge } from "@/components/ai/ai-badge";
import { StatePanel } from "@/components/data-display/state-panel";
import { FormField } from "@/components/forms/form-field";
import { Textarea } from "@/components/forms/textarea";
import { PageHeader } from "@/components/page-header";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getAgent, orchestrateAgent } from "@/lib/api/agents";
import { ApiError } from "@/lib/api/client";
import { getLead } from "@/lib/api/leads";
import type { Agent, Lead, OrchestrationResult } from "@/types/api";

const statusToBadge = {
  DRAFT: "draft",
  READY: "ready",
  ACTIVE: "active",
  PAUSED: "paused",
  NEEDS_ATTENTION: "needs-attention",
} as const;

export default function AgentWorkspacePage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const agentId = typeof params.id === "string" ? params.id : "";
  const leadId = searchParams.get("lead")?.trim() ?? "";
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(() => Boolean(agentId));
  const [notFound, setNotFound] = useState(() => !agentId);
  const [loadError, setLoadError] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<OrchestrationResult | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [boundLead, setBoundLead] = useState<Lead | null>(null);
  const [leadLoading, setLeadLoading] = useState(() => Boolean(leadId));
  const [leadMissing, setLeadMissing] = useState(false);
  const [leadError, setLeadError] = useState(false);

  useEffect(() => {
    if (!agentId) return;
    let cancelled = false;
    void getAgent(agentId)
      .then((data) => {
        if (cancelled) return;
        setAgent(data);
        setNotFound(false);
        setLoadError(false);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setAgent(null);
        if (cause instanceof ApiError && cause.status === 404) {
          setNotFound(true);
          setLoadError(false);
        } else {
          setNotFound(false);
          setLoadError(true);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId]);

  useEffect(() => {
    if (!leadId) return;
    let cancelled = false;
    void getLead(leadId)
      .then((data) => {
        if (cancelled) return;
        setBoundLead(data);
        setLeadMissing(false);
        setLeadError(false);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setBoundLead(null);
        if (cause instanceof ApiError && cause.status === 404) {
          setLeadMissing(true);
          setLeadError(false);
        } else {
          setLeadMissing(false);
          setLeadError(true);
        }
      })
      .finally(() => {
        if (!cancelled) setLeadLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [leadId]);

  async function handleRun(instruction: string) {
    if (!agent || isRunning) return;
    setIsRunning(true);
    setRequestError(null);
    setResult(null);
    try {
      const next = await orchestrateAgent(agent.id, {
        instruction,
        ...(boundLead ? { lead_id: boundLead.id } : {}),
      });
      setResult(next);
    } catch (cause) {
      setRequestError(orchestrationErrorMessage(cause));
    } finally {
      setIsRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="gap-section flex flex-col">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="gap-section flex flex-col">
        <PageHeader
          breadcrumbs={[
            { label: "AI Agents", href: "/agents" },
            { label: notFound ? "Agent not found" : "Agent unavailable" },
          ]}
          title={notFound ? "Agent not found" : "Agent unavailable"}
        />
        <StatePanel
          kind={notFound ? "unavailable" : "error"}
          title={notFound ? "Agent not found" : "Agent could not be loaded"}
          description={
            notFound
              ? "Return to AI Agents to select an available agent."
              : "Check your connection and try again."
          }
          action={
            <Link href="/agents" className={buttonVariants({ variant: "outline" })}>
              Back to AI Agents
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="gap-section mx-auto flex w-full max-w-3xl flex-col">
      <PageHeader
        breadcrumbs={[
          { label: "AI Agents", href: "/agents" },
          { label: agent.name, href: `/agents/${agent.id}` },
          { label: "Workspace" },
        ]}
        title="Agent Workspace"
        description={
          agent.description ||
          "Submit one instruction. FlowPilot plans and executes a single controlled run."
        }
        secondaryActions={
          <div className="flex flex-wrap items-center gap-2">
            <AiBadge label="Agent" />
            <AgentStatusBadge status={statusToBadge[agent.status]} />
          </div>
        }
        primaryAction={
          <Link
            href={`/agents/${agent.id}`}
            className={buttonVariants({ variant: "outline" })}
          >
            Agent settings
          </Link>
        }
      />

      <div className="border-border bg-surface-subtle rounded-lg border px-4 py-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
              Running as
            </p>
            <p className="mt-1 text-sm font-medium">{agent.name}</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
              Agent type
            </p>
            <p className="mt-1 text-sm font-medium">{agent.agent_type}</p>
          </div>
        </div>
      </div>

      {leadId && leadLoading ? <Skeleton className="h-28 w-full" /> : null}
      {leadId && leadMissing ? (
        <StatePanel
          kind="unavailable"
          title="Lead not found"
          description="This copilot run stays on the lead selected from Customer 360."
          action={
            <Link href="/leads" className={buttonVariants({ variant: "outline" })}>
              Back to Leads
            </Link>
          }
        />
      ) : null}
      {leadId && leadError ? (
        <StatePanel
          kind="error"
          title="Lead could not be loaded"
          description="Check your connection and open Customer 360 again."
        />
      ) : null}
      {boundLead ? (
        <section
          aria-labelledby="stored-enquiry-title"
          className="border-border bg-card grid gap-3 rounded-lg border p-4"
        >
          <div className="grid gap-1">
            <h2 id="stored-enquiry-title" className="text-sm font-semibold">
              Stored enquiry
            </h2>
            <p className="text-muted-foreground text-xs leading-5">
              Qualification and drafting use this text from {boundLead.name}. It
              cannot be edited here, and this screen does not send email.
            </p>
          </div>
          <FormField label="Enquiry" htmlFor="agent-workspace-stored-enquiry">
            <Textarea
              id="agent-workspace-stored-enquiry"
              value={boundLead.enquiry?.trim() ?? ""}
              readOnly
              aria-readonly="true"
              placeholder="No enquiry is stored for this lead."
            />
          </FormField>
        </section>
      ) : null}

      {loadError || (leadId && !boundLead) ? null : (
        <AgentWorkspacePanel
          agentStatus={agent.status}
          isRunning={isRunning}
          result={result}
          requestError={requestError}
          onRun={(instruction) => {
            void handleRun(instruction);
          }}
        />
      )}
    </div>
  );
}
