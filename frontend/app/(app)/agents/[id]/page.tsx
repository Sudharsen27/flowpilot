"use client";

import { Save } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AgentCapabilities } from "@/components/agents/agent-capabilities";
import { AgentCommunication } from "@/components/agents/agent-communication";
import { AgentConfigurationSidebar } from "@/components/agents/agent-configuration-sidebar";
import { AgentIdentityForm } from "@/components/agents/agent-identity-form";
import { AgentInstructions } from "@/components/agents/agent-instructions";
import { AgentResources } from "@/components/agents/agent-resources";
import { AgentSafety } from "@/components/agents/agent-safety";
import { StatePanel } from "@/components/data-display/state-panel";
import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AgentStatusBadge } from "@/components/agents/agent-status-badge";
import { ApiError } from "@/lib/api/client";
import { getAgent } from "@/lib/api/agents";
import type { Agent } from "@/types/api";

const statusToBadge = {
  DRAFT: "draft",
  READY: "ready",
  ACTIVE: "active",
  PAUSED: "paused",
  NEEDS_ATTENTION: "needs-attention",
} as const;

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const agentId = params.id;
  const [agent, setAgent] = useState<Agent | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorKind, setErrorKind] = useState<"not-found" | "error" | null>(
    null,
  );
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void getAgent(agentId)
      .then((data) => {
        if (!cancelled) setAgent(data);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setAgent(null);
          setErrorKind(
            error instanceof ApiError && error.status === 404
              ? "not-found"
              : "error",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, retryKey]);

  if (isLoading) {
    return (
      <div className="gap-section flex flex-col" role="status">
        <PageHeader
          breadcrumbs={[
            { label: "AI Agents", href: "/agents" },
            { label: "Loading agent" },
          ]}
          title="Loading agent"
          description="Loading the current agent configuration."
        />
        <Skeleton className="h-40" />
        <Skeleton className="h-80" />
        <span className="sr-only">Loading agent details</span>
      </div>
    );
  }

  if (!agent) {
    const notFound = errorKind === "not-found";
    return (
      <div className="gap-section flex flex-col">
        <PageHeader
          breadcrumbs={[
            { label: "AI Agents", href: "/agents" },
            { label: notFound ? "Agent not found" : "Agent unavailable" },
          ]}
          title={notFound ? "Agent not found" : "Agent unavailable"}
          description={
            notFound
              ? "This agent does not exist or is not available in your organization."
              : "The agent could not be loaded."
          }
        />
        <StatePanel
          kind="error"
          className="max-w-none"
          title={notFound ? "Agent not found" : "Agent could not be loaded"}
          description={
            notFound
              ? "Return to AI Agents to select an available agent."
              : "Check your connection and try again."
          }
          action={
            <div className="flex flex-wrap gap-2">
              {!notFound ? (
                <Button
                  type="button"
                  onClick={() => {
                    setIsLoading(true);
                    setErrorKind(null);
                    setRetryKey((key) => key + 1);
                  }}
                >
                  Retry
                </Button>
              ) : null}
              <Link
                href="/agents"
                className={buttonVariants({ variant: "outline" })}
              >
                Back to AI Agents
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  const badgeStatus = statusToBadge[agent.status];

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        breadcrumbs={[
          { label: "AI Agents", href: "/agents" },
          { label: agent.name },
        ]}
        title={agent.name}
        description={agent.description || "No description provided."}
        secondaryActions={<AgentStatusBadge status={badgeStatus} />}
        primaryAction={
          <>
            <Button
              type="button"
              disabled
              aria-describedby="agent-save-unavailable"
            >
              <Save aria-hidden="true" />
              Save configuration
            </Button>
            <span id="agent-save-unavailable" className="sr-only">
              Editing and saving are not connected yet.
            </span>
          </>
        }
      />

      <StatePanel
        kind="unavailable"
        className="max-w-none"
        title="Configuration editing is not connected"
        description="This agent is loaded from the API and shown read-only. Changes and lifecycle actions will be connected in a later update."
      />

      <div
        data-slot="agent-detail-layout"
        className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]"
      >
        <div className="grid min-w-0 gap-6">
          <AgentIdentityForm
            name={agent.name}
            description={agent.description}
            agentType={agent.agent_type}
          />
          <AgentInstructions instructions={agent.system_instructions} />
          <AgentCapabilities />
          <AgentResources />
          <AgentSafety />
          <AgentCommunication />
        </div>
        <AgentConfigurationSidebar status={badgeStatus} />
      </div>
    </div>
  );
}
