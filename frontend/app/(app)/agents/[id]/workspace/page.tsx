"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AgentStatusBadge } from "@/components/agents/agent-status-badge";
import {
  AgentWorkspacePanel,
  orchestrationErrorMessage,
} from "@/components/agents/agent-workspace-panel";
import { AiBadge } from "@/components/ai/ai-badge";
import { StatePanel } from "@/components/data-display/state-panel";
import { PageHeader } from "@/components/page-header";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getAgent, orchestrateAgent } from "@/lib/api/agents";
import { ApiError } from "@/lib/api/client";
import type { Agent, OrchestrationResult } from "@/types/api";

const statusToBadge = {
  DRAFT: "draft",
  READY: "ready",
  ACTIVE: "active",
  PAUSED: "paused",
  NEEDS_ATTENTION: "needs-attention",
} as const;

export default function AgentWorkspacePage() {
  const params = useParams<{ id: string }>();
  const agentId = typeof params.id === "string" ? params.id : "";
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(() => Boolean(agentId));
  const [notFound, setNotFound] = useState(() => !agentId);
  const [loadError, setLoadError] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<OrchestrationResult | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);

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

  async function handleRun(instruction: string) {
    if (!agent || isRunning) return;
    setIsRunning(true);
    setRequestError(null);
    setResult(null);
    try {
      const next = await orchestrateAgent(agent.id, { instruction });
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

      {loadError ? null : (
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
