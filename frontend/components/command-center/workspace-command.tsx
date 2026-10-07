"use client";

import { type FormEvent, useMemo, useState } from "react";

import { AgentRunTrace } from "@/components/agents/agent-run-trace";
import { AgentWorkspaceResult } from "@/components/agents/agent-workspace-result";
import { orchestrationErrorMessage } from "@/components/agents/agent-workspace-panel";
import { Button } from "@/components/ui/button";
import { orchestrateAgent } from "@/lib/api/agents";
import type { Agent, OrchestrationResult } from "@/types/api";

const INSTRUCTION_MAX_LENGTH = 8000;

type WorkspaceCommandProps = {
  loading?: boolean;
  agents: Agent[];
};

export function WorkspaceCommand({ loading = false, agents }: WorkspaceCommandProps) {
  const runnable = useMemo(
    () => agents.filter((agent) => agent.status === "READY" || agent.status === "ACTIVE"),
    [agents],
  );
  const [agentId, setAgentId] = useState("");
  const [instruction, setInstruction] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OrchestrationResult | null>(null);

  const selectedId = runnable.some((agent) => agent.id === agentId)
    ? agentId
    : (runnable[0]?.id ?? "");
  const trimmed = instruction.trim();
  const tooLong = instruction.length > INSTRUCTION_MAX_LENGTH;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!selectedId || !trimmed || tooLong || isRunning) return;
    setIsRunning(true);
    setError(null);
    setResult(null);
    try {
      setResult(await orchestrateAgent(selectedId, { instruction: trimmed }));
    } catch (cause) {
      setError(orchestrationErrorMessage(cause));
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <section
      aria-labelledby="workspace-command-heading"
      className="border-border bg-card shadow-card overflow-hidden rounded-xl border"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 sm:px-6">
        <div>
          <h2 id="workspace-command-heading" className="text-section-title font-semibold tracking-tight">
            Ask FlowPilot
          </h2>
          <p className="text-muted-foreground mt-1 max-w-2xl text-sm leading-6">
            Give one instruction. The agent prepares the work and stops when a person must approve a send.
          </p>
        </div>
        <span className="bg-ai/10 text-ai-text border-ai-border inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium">
          Approval required before send
        </span>
      </div>

      {loading ? (
        <p className="text-muted-foreground px-5 py-6 text-sm sm:px-6" role="status">
          Loading agents…
        </p>
      ) : runnable.length === 0 ? (
        <p className="text-muted-foreground px-5 py-6 text-sm leading-6 sm:px-6">
          Mark a Sales Agent ready before running instructions from here.
        </p>
      ) : (
        <form onSubmit={onSubmit} className="grid gap-3 px-5 py-5 sm:px-6">
          <label className="grid gap-1.5">
            <span className="sr-only">Instruction</span>
            <textarea
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              placeholder="Qualify today’s new leads, or draft a reply for a waiting enquiry."
              rows={3}
              disabled={isRunning}
              className="border-input bg-background placeholder:text-muted-foreground focus-visible:ring-ring min-h-24 w-full resize-y rounded-lg border px-3 py-2.5 text-sm leading-6 outline-none focus-visible:ring-2"
            />
          </label>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <label className="text-muted-foreground flex min-w-0 items-center gap-2 text-xs">
              <span className="shrink-0">Agent</span>
              <select
                aria-label="Agent"
                value={selectedId}
                disabled={isRunning}
                onChange={(event) => setAgentId(event.target.value)}
                className="border-input bg-background text-foreground h-8 max-w-full rounded-md border px-2 text-sm"
              >
                {runnable.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
            </label>
            <Button type="submit" disabled={!trimmed || tooLong || isRunning}>
              {isRunning ? "Running" : "Run instruction"}
            </Button>
          </div>
          {tooLong ? (
            <p className="text-danger-text text-sm" role="alert">
              Keep the instruction under {INSTRUCTION_MAX_LENGTH} characters.
            </p>
          ) : null}
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
        </form>
      )}

      {isRunning ? (
        <div className="border-border border-t px-5 py-5 sm:px-6">
          <AgentRunTrace />
        </div>
      ) : null}

      {result && !isRunning ? (
        <div className="border-border border-t px-5 py-5 sm:px-6">
          <AgentWorkspaceResult result={result} />
        </div>
      ) : null}
    </section>
  );
}
