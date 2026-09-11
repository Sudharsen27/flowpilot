"use client";

import { Save } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { AgentCapabilities } from "@/components/agents/agent-capabilities";
import { AgentCommunication } from "@/components/agents/agent-communication";
import { AgentConfigurationSidebar } from "@/components/agents/agent-configuration-sidebar";
import { AgentExecutionHistory } from "@/components/agents/agent-execution-history";
import {
  AgentExecutionPanel,
  cancellationErrorMessage,
  executionErrorMessage,
} from "@/components/agents/agent-execution-panel";
import { AgentIdentityForm } from "@/components/agents/agent-identity-form";
import { AgentInstructions } from "@/components/agents/agent-instructions";
import { AgentResources } from "@/components/agents/agent-resources";
import { AgentSafety } from "@/components/agents/agent-safety";
import { StatePanel } from "@/components/data-display/state-panel";
import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AgentStatusBadge } from "@/components/agents/agent-status-badge";
import { AiBadge } from "@/components/ai/ai-badge";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import {
  activateAgent,
  cancelAgentExecution,
  createAgentExecution,
  getAgent,
  markAgentReady,
  pauseAgent,
  runAgentExecution,
  updateAgent,
} from "@/lib/api/agents";
import type {
  Agent,
  AgentExecutionResult,
  AgentType,
  AgentUpdateRequest,
} from "@/types/api";

const statusToBadge = {
  DRAFT: "draft",
  READY: "ready",
  ACTIVE: "active",
  PAUSED: "paused",
  NEEDS_ATTENTION: "needs-attention",
} as const;

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const { session } = useAuth();
  const agentId = params.id;
  const [agent, setAgent] = useState<Agent | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorKind, setErrorKind] = useState<"not-found" | "error" | null>(
    null,
  );
  const [retryKey, setRetryKey] = useState(0);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [agentType, setAgentType] = useState<AgentType>("SALES");
  const [instructions, setInstructions] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [isLifecyclePending, setIsLifecyclePending] = useState(false);
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);
  const [lifecycleSuccess, setLifecycleSuccess] = useState<string | null>(
    null,
  );
  const [isExecuting, setIsExecuting] = useState(false);
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(
    null,
  );
  const [isCancelling, setIsCancelling] = useState(false);
  const [executionResult, setExecutionResult] =
    useState<AgentExecutionResult | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const lifecyclePendingRef = useRef(false);
  const executionPendingRef = useRef(false);
  const cancelPendingRef = useRef(false);
  const canEdit =
    session?.membership.role === "OWNER" ||
    session?.membership.role === "ADMIN";

  useEffect(() => {
    let cancelled = false;
    void getAgent(agentId)
      .then((data) => {
        if (!cancelled) {
          setAgent(data);
          setName(data.name);
          setDescription(data.description);
          setAgentType(data.agent_type);
          setInstructions(data.system_instructions);
        }
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

  const isDirty = useMemo(
    () =>
      agent !== null &&
      (name !== agent.name ||
        description !== agent.description ||
        agentType !== agent.agent_type ||
        instructions !== agent.system_instructions),
    [agent, agentType, description, instructions, name],
  );

  useEffect(() => {
    function warnBeforeUnload(event: BeforeUnloadEvent) {
      if (isDirty) {
        event.preventDefault();
      }
    }
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [isDirty]);

  async function handleLifecycle(action: "ready" | "activate" | "pause") {
    if (
      !agent ||
      !canEdit ||
      lifecyclePendingRef.current ||
      isSaving ||
      isExecuting
    )
      return;
    lifecyclePendingRef.current = true;
    setLifecycleError(null);
    setLifecycleSuccess(null);
    setIsLifecyclePending(true);
    try {
      const updated =
        action === "ready"
          ? await markAgentReady(agent.id)
          : action === "activate"
            ? await activateAgent(agent.id)
            : await pauseAgent(agent.id);
      setAgent(updated);
      setLifecycleSuccess(
        action === "ready"
          ? "Agent marked ready."
          : action === "activate"
            ? "Agent activated."
            : "Agent paused.",
      );
    } catch (cause) {
      setLifecycleError(
        cause instanceof ApiError && cause.status === 403
          ? "You do not have permission to change this agent's status."
          : cause instanceof ApiError && cause.status === 409
            ? "This status change is not allowed for the current agent."
            : "The agent status could not be updated. Please try again.",
      );
    } finally {
      lifecyclePendingRef.current = false;
      setIsLifecyclePending(false);
    }
  }

  async function handleSave() {
    if (
      !agent ||
      !canEdit ||
      !isDirty ||
      isSaving ||
      isLifecyclePending ||
      isExecuting
    )
      return;
    const changes: AgentUpdateRequest = {};
    if (name !== agent.name) changes.name = name.trim();
    if (description !== agent.description) {
      changes.description = description.trim();
    }
    if (agentType !== agent.agent_type) changes.agent_type = agentType;
    if (instructions !== agent.system_instructions) {
      changes.system_instructions = instructions;
    }
    setSaveError(null);
    setSaved(false);
    setIsSaving(true);
    try {
      const updated = await updateAgent(agent.id, changes);
      setAgent(updated);
      setName(updated.name);
      setDescription(updated.description);
      setAgentType(updated.agent_type);
      setInstructions(updated.system_instructions);
      setSaved(true);
    } catch (cause) {
      setSaveError(
        cause instanceof ApiError && cause.status === 403
          ? "You do not have permission to update this agent."
          : cause instanceof ApiError && cause.status === 422
            ? "Review the configuration and correct invalid fields."
            : "The configuration could not be saved. Please try again.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function handleExecute(input: string) {
    if (!agent || executionPendingRef.current || isSaving || isLifecyclePending)
      return;
    if (agent.status !== "READY" && agent.status !== "ACTIVE") return;
    executionPendingRef.current = true;
    cancelPendingRef.current = false;
    setExecutionError(null);
    setIsExecuting(true);
    setActiveExecutionId(null);
    setIsCancelling(false);
    try {
      const started = await createAgentExecution(agent.id, { input });
      setActiveExecutionId(started.execution_id);
      setHistoryRefreshKey((key) => key + 1);
      const result = await runAgentExecution(agent.id, started.execution_id);
      setExecutionResult(result);
      setHistoryRefreshKey((key) => key + 1);
    } catch (cause) {
      if (
        cancelPendingRef.current &&
        cause instanceof ApiError &&
        cause.status === 409
      ) {
        setHistoryRefreshKey((key) => key + 1);
      } else {
        setExecutionError(executionErrorMessage(cause));
        if (
          cause instanceof ApiError &&
          (cause.status === 502 || cause.status === 503)
        ) {
          setHistoryRefreshKey((key) => key + 1);
        }
      }
    } finally {
      executionPendingRef.current = false;
      setIsExecuting(false);
      setActiveExecutionId(null);
      setIsCancelling(false);
    }
  }

  async function handleCancel() {
    if (!agent || !activeExecutionId || cancelPendingRef.current) return;
    cancelPendingRef.current = true;
    setIsCancelling(true);
    setExecutionError(null);
    try {
      const result = await cancelAgentExecution(agent.id, activeExecutionId);
      setExecutionResult(result);
      setHistoryRefreshKey((key) => key + 1);
    } catch (cause) {
      cancelPendingRef.current = false;
      setExecutionError(cancellationErrorMessage(cause));
    } finally {
      setIsCancelling(false);
    }
  }

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
        secondaryActions={
          <div className="flex flex-wrap items-center gap-2">
            <AiBadge label="Agent" />
            <AgentStatusBadge status={badgeStatus} />
          </div>
        }
        primaryAction={
          <>
            <Button
              type="button"
              disabled={
                !canEdit ||
                !isDirty ||
                isSaving ||
                isLifecyclePending ||
                isExecuting ||
                !name.trim()
              }
              onClick={() => void handleSave()}
              aria-describedby={!canEdit ? "agent-save-unavailable" : undefined}
            >
              <Save aria-hidden="true" />
              {isSaving ? "Saving…" : "Save configuration"}
            </Button>
            <span id="agent-save-unavailable" className="sr-only">
              Your role has read-only access to agent configuration.
            </span>
          </>
        }
      />

      {saveError ? (
        <p className="text-danger-text text-sm" role="alert">
          {saveError}
        </p>
      ) : saved ? (
        <p className="text-success-text text-sm" role="status">
          Configuration saved.
        </p>
      ) : lifecycleError ? (
        <p className="text-danger-text text-sm" role="alert">
          {lifecycleError}
        </p>
      ) : lifecycleSuccess ? (
        <p className="text-success-text text-sm" role="status">
          {lifecycleSuccess}
        </p>
      ) : !canEdit ? (
        <StatePanel
          kind="information"
          className="max-w-none"
          title="Read-only configuration"
          description="Your membership role can view this agent but cannot update its configuration."
        />
      ) : null}

      <div
        data-slot="agent-detail-layout"
        className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]"
      >
        <div className="grid min-w-0 gap-6">
          <AgentIdentityForm
            name={name}
            description={description}
            agentType={agentType}
            editable={canEdit}
            onNameChange={(value) => {
              setName(value);
              setSaved(false);
            }}
            onDescriptionChange={(value) => {
              setDescription(value);
              setSaved(false);
            }}
            onAgentTypeChange={(value) => {
              setAgentType(value);
              setSaved(false);
            }}
          />
          <AgentInstructions
            instructions={instructions}
            editable={canEdit}
            onChange={(value) => {
              setInstructions(value);
              setSaved(false);
            }}
          />
          <AgentExecutionPanel
            agentStatus={agent.status}
            isBusy={isSaving || isLifecyclePending}
            isRunning={isExecuting}
            isCancelling={isCancelling}
            canCancel={
              Boolean(activeExecutionId) &&
              isExecuting &&
              executionResult?.status !== "CANCELLED"
            }
            result={executionResult}
            error={executionError}
            onRun={handleExecute}
            onCancel={() => void handleCancel()}
          />
          <AgentExecutionHistory
            key={historyRefreshKey}
            agentId={agent.id}
          />
          <AgentCapabilities />
          <AgentResources />
          <AgentSafety />
          <AgentCommunication />
        </div>
        <AgentConfigurationSidebar
          status={badgeStatus}
          apiStatus={agent.status}
          canEdit={canEdit}
          isDirty={isDirty}
          isSaving={isSaving}
          isLifecyclePending={isLifecyclePending || isExecuting}
          onSave={() => void handleSave()}
          onReady={() => void handleLifecycle("ready")}
          onActivate={() => void handleLifecycle("activate")}
          onPause={() => void handleLifecycle("pause")}
        />
      </div>
    </div>
  );
}
