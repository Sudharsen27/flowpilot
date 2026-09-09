"use client";

import { useEffect, useRef, useState } from "react";

import { AgentToolInvocationList } from "@/components/agents/agent-tool-invocation-list";
import {
  ExecutionStatusBadge,
  formatDuration,
  formatFailureCategory,
  formatTimestamp,
  historyErrorMessage,
} from "@/components/agents/execution-status";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getAgentExecution } from "@/lib/api/agents";
import type { AgentExecutionDetail } from "@/types/api";

type AgentExecutionDetailPanelProps = {
  agentId: string;
  executionId: string;
  onClose: () => void;
};

export function AgentExecutionDetailPanel({
  agentId,
  executionId,
  onClose,
}: AgentExecutionDetailPanelProps) {
  const [detail, setDetail] = useState<AgentExecutionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, [executionId]);

  useEffect(() => {
    let cancelled = false;
    void getAgentExecution(agentId, executionId)
      .then((data) => {
        if (!cancelled) {
          setDetail(data);
          setError(null);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(
            historyErrorMessage(
              cause,
              "This execution could not be loaded. Please try again.",
              "This execution could not be found.",
            ),
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, executionId, retryKey]);

  const usageTotal = detail?.usage?.total_tokens;

  return (
    <section
      className="border-border grid gap-4 rounded-md border p-4"
      aria-labelledby="execution-history-detail-title"
      aria-busy={!detail && !error ? true : undefined}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3
          ref={headingRef}
          id="execution-history-detail-title"
          tabIndex={-1}
          className="text-sm font-semibold outline-none"
        >
          Execution detail
        </h3>
        <Button type="button" variant="outline" onClick={onClose}>
          Back to history
        </Button>
      </div>
      {error ? (
        <div className="grid gap-2">
          <p id="execution-detail-error" className="text-danger-text text-sm" role="alert">
            {error}
          </p>
          <Button
            type="button"
            variant="outline"
            aria-describedby="execution-detail-error"
            onClick={() => {
              setDetail(null);
              setError(null);
              setRetryKey((key) => key + 1);
            }}
          >
            Retry execution
          </Button>
        </div>
      ) : !detail ? (
        <div role="status" aria-live="polite" aria-busy="true" className="grid gap-2">
          <Skeleton className="h-40" />
          <span className="sr-only">Loading execution detail</span>
        </div>
      ) : (
        <div className="grid min-w-0 gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <ExecutionStatusBadge status={detail.status} />
            <p className="font-mono text-xs break-all">{detail.id}</p>
          </div>
          <dl className="grid gap-3 text-sm">
            {formatDuration(detail.duration_ms) ? (
              <div className="grid gap-1">
                <dt className="text-muted-foreground">Duration</dt>
                <dd>{formatDuration(detail.duration_ms)}</dd>
              </div>
            ) : null}
            {formatFailureCategory(detail.failure_category) ? (
              <div className="grid gap-1">
                <dt className="text-muted-foreground">Failure category</dt>
                <dd>{formatFailureCategory(detail.failure_category)}</dd>
              </div>
            ) : null}
            {detail.provider ? (
              <div className="grid gap-1">
                <dt className="text-muted-foreground">Provider</dt>
                <dd>{detail.provider}</dd>
              </div>
            ) : null}
            {detail.model ? (
              <div className="grid gap-1">
                <dt className="text-muted-foreground">Model</dt>
                <dd>{detail.model}</dd>
              </div>
            ) : null}
            {typeof usageTotal === "number" ? (
              <div className="grid gap-1">
                <dt className="text-muted-foreground">Provider token usage</dt>
                <dd>{usageTotal}</dd>
              </div>
            ) : null}
            {detail.initiated_by_user_id ? (
              <div className="grid gap-1">
                <dt className="text-muted-foreground">Initiated by user</dt>
                <dd className="font-mono text-xs break-all">
                  {detail.initiated_by_user_id}
                </dd>
              </div>
            ) : null}
            <div className="grid gap-1">
              <dt className="text-muted-foreground">Created</dt>
              <dd>
                <time dateTime={detail.created_at}>
                  {formatTimestamp(detail.created_at)}
                </time>
              </dd>
            </div>
            {detail.started_at ? (
              <div className="grid gap-1">
                <dt className="text-muted-foreground">Started</dt>
                <dd>
                  <time dateTime={detail.started_at}>
                    {formatTimestamp(detail.started_at)}
                  </time>
                </dd>
              </div>
            ) : null}
            {detail.completed_at ? (
              <div className="grid gap-1">
                <dt className="text-muted-foreground">Completed</dt>
                <dd>
                  <time dateTime={detail.completed_at}>
                    {formatTimestamp(detail.completed_at)}
                  </time>
                </dd>
              </div>
            ) : null}
          </dl>
          <div className="grid min-w-0 gap-1">
            <h4 className="text-muted-foreground text-sm font-medium">Input</h4>
            {detail.input ? (
              <pre className="bg-muted max-h-80 overflow-auto rounded-md p-3 text-sm leading-6 whitespace-pre-wrap">
                {detail.input}
              </pre>
            ) : (
              <p className="text-muted-foreground text-sm">No input returned.</p>
            )}
          </div>
          <div className="grid min-w-0 gap-1">
            <h4 className="text-muted-foreground text-sm font-medium">Output</h4>
            {detail.output ? (
              <pre className="bg-muted max-h-80 overflow-auto rounded-md p-3 text-sm leading-6 whitespace-pre-wrap">
                {detail.output}
              </pre>
            ) : (
              <p className="text-muted-foreground text-sm">No output returned.</p>
            )}
          </div>
          {detail.error ? (
            <p className="text-danger-text text-sm" role="alert">
              {detail.error}
            </p>
          ) : null}
          <AgentToolInvocationList
            key={detail.id}
            agentId={agentId}
            executionId={detail.id}
          />
        </div>
      )}
    </section>
  );
}
