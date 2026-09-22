"use client";

import { Play } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { AgentWorkspaceResult } from "@/components/agents/agent-workspace-result";
import { FormField } from "@/components/forms/form-field";
import { Textarea } from "@/components/forms/textarea";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import type { AgentStatus, OrchestrationResult } from "@/types/api";

export const INSTRUCTION_MAX_LENGTH = 8000;

const unavailableCopy: Partial<Record<AgentStatus, string>> = {
  DRAFT: "Draft agents cannot run the workspace. Mark the agent ready first.",
  PAUSED: "Paused agents cannot run the workspace. Resume the agent first.",
  NEEDS_ATTENTION:
    "This agent needs attention and cannot run instructions from this screen.",
};

export function orchestrationErrorMessage(cause: unknown) {
  if (cause instanceof ApiError) {
    if (cause.status === 401) {
      return "Your session has expired. Sign in again to run this agent.";
    }
    if (cause.status === 403) {
      return "You do not have permission to run this agent.";
    }
    if (cause.status === 404) {
      return "This agent could not be found.";
    }
    if (cause.status === 422) {
      return "Review the instruction and try again.";
    }
    if (cause.status === 502 || cause.status === 503) {
      return "Something went wrong while running the agent.";
    }
  }
  return "Something went wrong while running the agent.";
}

type AgentWorkspacePanelProps = {
  agentStatus: AgentStatus;
  isRunning: boolean;
  result: OrchestrationResult | null;
  requestError: string | null;
  onRun: (instruction: string) => void;
};

export function AgentWorkspacePanel({
  agentStatus,
  isRunning,
  result,
  requestError,
  onRun,
}: AgentWorkspacePanelProps) {
  const [instruction, setInstruction] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const submitGuardRef = useRef(false);
  const canRun = agentStatus === "READY" || agentStatus === "ACTIVE";
  const unavailable = unavailableCopy[agentStatus];
  const trimmed = instruction.trim();
  const tooLong = instruction.length > INSTRUCTION_MAX_LENGTH;
  const controlsLocked = isRunning || !canRun;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (controlsLocked || submitGuardRef.current) return;
    if (!trimmed) {
      setInputError("Enter an instruction before running the agent.");
      return;
    }
    if (tooLong) {
      setInputError(
        `Instruction must be ${INSTRUCTION_MAX_LENGTH} characters or fewer.`,
      );
      return;
    }
    setInputError(null);
    submitGuardRef.current = true;
    onRun(trimmed);
  }

  useEffect(() => {
    if (!isRunning) {
      submitGuardRef.current = false;
    }
  }, [isRunning]);

  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader>
          <CardTitle id="agent-workspace-command-title">Instruction</CardTitle>
          <CardDescription>
            Describe what you want this agent to do. FlowPilot plans and runs a
            single controlled workflow — this is not a chat thread.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {unavailable ? (
            <p className="text-muted-foreground text-sm" role="status">
              {unavailable}
            </p>
          ) : (
            <form className="grid gap-4" onSubmit={submit} noValidate>
              <FormField
                label="What would you like me to do?"
                htmlFor="agent-workspace-instruction"
                error={inputError}
                required
              >
                <Textarea
                  id="agent-workspace-instruction"
                  name="instruction"
                  value={instruction}
                  onChange={(event) => {
                    setInstruction(event.target.value);
                    if (inputError) setInputError(null);
                  }}
                  placeholder="Find new website leads from today and qualify them."
                  disabled={controlsLocked}
                  aria-invalid={Boolean(inputError) || undefined}
                  maxLength={INSTRUCTION_MAX_LENGTH + 1}
                  className="min-h-32"
                />
              </FormField>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-muted-foreground text-xs">
                  {instruction.length} / {INSTRUCTION_MAX_LENGTH}
                </p>
                <Button
                  type="submit"
                  disabled={controlsLocked || !trimmed || tooLong}
                  aria-busy={isRunning || undefined}
                >
                  <Play aria-hidden="true" />
                  {isRunning ? "Running…" : "Run Agent"}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>

      {isRunning ? (
        <div
          className="border-border bg-card shadow-card rounded-xl border p-5 sm:p-6"
          role="status"
          aria-live="polite"
        >
          <p className="text-sm font-medium">Running your instruction…</p>
          <p className="text-muted-foreground mt-1.5 text-sm leading-6">
            Planning and executing the requested workflow.
          </p>
        </div>
      ) : null}

      {requestError ? (
        <p className="text-danger-text text-sm" role="alert">
          {requestError}
        </p>
      ) : null}

      {result && !isRunning ? <AgentWorkspaceResult result={result} /> : null}
    </div>
  );
}
