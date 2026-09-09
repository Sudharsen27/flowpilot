"use client";

import { Play } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import {
  ExecutionStatusBadge,
  formatDuration,
  formatFailureCategory,
} from "@/components/agents/execution-status";
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
import type { AgentExecutionResult, AgentStatus } from "@/types/api";

const unavailableCopy: Partial<Record<AgentStatus, string>> = {
  DRAFT: "Draft agents cannot be executed. Mark the agent ready first.",
  PAUSED: "Paused agents cannot be executed. Resume the agent first.",
  NEEDS_ATTENTION:
    "This agent needs attention and cannot be executed from this screen.",
};

export function executionErrorMessage(cause: unknown) {
  if (cause instanceof ApiError) {
    if (cause.status === 400) {
      return "This agent cannot be executed in its current status.";
    }
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
      return "Review the execution input and try again.";
    }
    if (cause.status === 502) {
      return "The AI provider could not complete this run.";
    }
    if (cause.status === 503) {
      return "The AI provider is not configured.";
    }
  }
  return "The agent could not be run. Check your connection and try again.";
}

type AgentExecutionPanelProps = {
  agentStatus: AgentStatus;
  isBusy: boolean;
  isRunning: boolean;
  result: AgentExecutionResult | null;
  error: string | null;
  onRun: (input: string) => void;
};

export function AgentExecutionPanel({
  agentStatus,
  isBusy,
  isRunning,
  result,
  error,
  onRun,
}: AgentExecutionPanelProps) {
  const [input, setInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const submitGuardRef = useRef(false);
  const canExecute = agentStatus === "READY" || agentStatus === "ACTIVE";
  const unavailable = unavailableCopy[agentStatus];
  const trimmed = input.trim();
  const controlsLocked = isBusy || isRunning;
  const canRetry =
    canExecute &&
    !controlsLocked &&
    Boolean(trimmed) &&
    (Boolean(error) || result?.status === "FAILED");

  function submitInput() {
    if (!canExecute || controlsLocked) return;
    if (!trimmed) {
      setInputError("Enter input before running the agent.");
      return;
    }
    submitGuardRef.current = true;
    setInputError(null);
    onRun(trimmed);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitInput();
  }

  useEffect(() => {
    if (!isRunning) {
      submitGuardRef.current = false;
    }
  }, [isRunning]);

  return (
    <Card
      as="section"
      aria-labelledby="run-agent-title"
      aria-busy={isRunning || undefined}
    >
      <CardHeader>
        <CardTitle id="run-agent-title">Run agent</CardTitle>
        <CardDescription>
          Sends this input to the connected AI provider and returns the real
          execution result. Recorded runs also appear in Execution history.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5">
        {!canExecute ? (
          <p className="text-muted-foreground text-sm leading-6">{unavailable}</p>
        ) : (
          <form
            className="grid gap-4"
            onSubmit={handleSubmit}
            aria-busy={isRunning || undefined}
          >
            <FormField
              label="Execution input"
              htmlFor="agent-execution-input"
              required
              error={inputError}
              description="Required. Sent as the execution input to the Agent API."
            >
              <Textarea
                id="agent-execution-input"
                value={input}
                onChange={(event) => {
                  setInput(event.target.value);
                  setInputError(null);
                }}
                maxLength={8000}
                disabled={isRunning}
                placeholder="Describe the task for this agent to complete."
                aria-invalid={inputError ? true : undefined}
                aria-describedby={
                  inputError
                    ? "agent-execution-input-error"
                    : "agent-execution-input-description"
                }
              />
            </FormField>
            <div className="flex flex-wrap gap-2">
              <Button
                type="submit"
                disabled={controlsLocked || !trimmed}
                aria-busy={isRunning || undefined}
              >
                <Play aria-hidden="true" />
                {isRunning ? "Running…" : "Run agent"}
              </Button>
              {canRetry ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => submitInput()}
                >
                  Try again
                </Button>
              ) : null}
            </div>
          </form>
        )}

        {isRunning ? (
          <div role="status" aria-live="polite" aria-busy="true" className="grid gap-1">
            <p className="text-sm font-medium">Running agent…</p>
            <p className="text-muted-foreground text-sm leading-6">
              Waiting for the execution request to finish. Do not close this
              page until it returns.
            </p>
            <span className="sr-only">Execution request in progress</span>
          </div>
        ) : null}

        {!isRunning && error ? (
          <p className="text-danger-text text-sm" role="alert">
            {error}
          </p>
        ) : null}

        {!isRunning && result ? (
          <ExecutionResult result={result} />
        ) : !isRunning && canExecute ? (
          <p className="text-muted-foreground text-sm leading-6">
            The latest result from this page session will appear here. Recorded
            runs are listed in Execution history.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ExecutionResult({ result }: { result: AgentExecutionResult }) {
  const usageTotal = result.usage?.total_tokens;
  const duration = formatDuration(result.duration_ms);
  const failure = formatFailureCategory(result.failure_category ?? null);

  return (
    <section
      className="border-border grid gap-4 rounded-md border p-4"
      aria-labelledby="execution-result-title"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="execution-result-title" className="text-sm font-semibold">
          Latest execution result
        </h3>
        <ExecutionStatusBadge status={result.status} />
      </div>
      <dl className="grid gap-3 text-sm">
        <div className="grid gap-1">
          <dt className="text-muted-foreground">Execution ID</dt>
          <dd className="font-mono text-xs break-all">{result.execution_id}</dd>
        </div>
        {duration ? (
          <div className="grid gap-1">
            <dt className="text-muted-foreground">Duration</dt>
            <dd>{duration}</dd>
          </div>
        ) : null}
        {failure && result.status === "FAILED" ? (
          <div className="grid gap-1">
            <dt className="text-muted-foreground">Failure category</dt>
            <dd>{failure}</dd>
          </div>
        ) : null}
        {result.provider ? (
          <div className="grid gap-1">
            <dt className="text-muted-foreground">Provider</dt>
            <dd>{result.provider}</dd>
          </div>
        ) : null}
        {result.model ? (
          <div className="grid gap-1">
            <dt className="text-muted-foreground">Model</dt>
            <dd>{result.model}</dd>
          </div>
        ) : null}
        {typeof usageTotal === "number" ? (
          <div className="grid gap-1">
            <dt className="text-muted-foreground">Provider token usage</dt>
            <dd>{usageTotal}</dd>
          </div>
        ) : null}
      </dl>
      {result.status === "COMPLETED" ? (
        <div className="grid gap-1">
          <h4 className="text-muted-foreground text-sm font-medium">Output</h4>
          {result.output ? (
            <pre className="bg-muted max-h-80 overflow-auto rounded-md p-3 text-sm leading-6 whitespace-pre-wrap">
              {result.output}
            </pre>
          ) : (
            <p className="text-muted-foreground text-sm">No output returned.</p>
          )}
        </div>
      ) : null}
      {result.status === "FAILED" && result.error ? (
        <p className="text-danger-text text-sm" role="alert">
          {result.error}
        </p>
      ) : null}
    </section>
  );
}
