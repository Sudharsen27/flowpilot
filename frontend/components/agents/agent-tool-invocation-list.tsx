"use client";

import { useEffect, useState } from "react";

import {
  ToolInvocationStatusBadge,
  formatTimestamp,
  historyErrorMessage,
} from "@/components/agents/execution-status";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { listToolInvocations } from "@/lib/api/agents";
import type { ToolInvocationListItem } from "@/types/api";

type AgentToolInvocationListProps = {
  agentId: string;
  executionId: string;
};

export function AgentToolInvocationList({
  agentId,
  executionId,
}: AgentToolInvocationListProps) {
  const [items, setItems] = useState<ToolInvocationListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void listToolInvocations(agentId, executionId, { limit: 50, offset: 0 })
      .then((page) => {
        if (!cancelled) {
          setItems(page.items);
          setError(null);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(
            historyErrorMessage(
              cause,
              "Tool activity could not be loaded. Please try again.",
              "Tool activity for this execution could not be found.",
            ),
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, executionId, retryKey]);

  return (
    <section className="grid gap-3" aria-labelledby="tool-activity-title">
      <h4 id="tool-activity-title" className="text-sm font-semibold">
        Tool activity
      </h4>
      {error ? (
        <div className="grid gap-2">
          <p id="tool-activity-error" className="text-danger-text text-sm" role="alert">
            {error}
          </p>
          <Button
            type="button"
            variant="outline"
            aria-describedby="tool-activity-error"
            onClick={() => {
              setItems(null);
              setError(null);
              setRetryKey((key) => key + 1);
            }}
          >
            Retry tool activity
          </Button>
        </div>
      ) : items === null ? (
        <div role="status" aria-live="polite" aria-busy="true" className="grid gap-2">
          <Skeleton className="h-16" />
          <span className="sr-only">Loading tool activity</span>
        </div>
      ) : items.length === 0 ? (
        <p className="text-muted-foreground text-sm leading-6">
          No tool activity recorded for this execution.
        </p>
      ) : (
        <ol className="grid gap-3">
          {items.map((item) => (
            <li
              key={item.id}
              className="border-border grid gap-2 rounded-md border p-3 text-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium">{item.tool_name}</p>
                <ToolInvocationStatusBadge status={item.status} />
              </div>
              <dl className="text-muted-foreground grid gap-1 text-xs">
                <div>
                  <dt className="inline">Call ID </dt>
                  <dd className="inline font-mono break-all">{item.call_id}</dd>
                </div>
                {item.risk_level ? (
                  <div>
                    <dt className="inline">Risk </dt>
                    <dd className="inline">{item.risk_level}</dd>
                  </div>
                ) : null}
                {item.decision ? (
                  <div>
                    <dt className="inline">Decision </dt>
                    <dd className="inline">{item.decision}</dd>
                  </div>
                ) : null}
                {item.argument_keys && item.argument_keys.length > 0 ? (
                  <div>
                    <dt className="inline">Argument keys </dt>
                    <dd className="inline">{item.argument_keys.join(", ")}</dd>
                  </div>
                ) : null}
                <div>
                  <dt className="inline">Started </dt>
                  <dd className="inline">{formatTimestamp(item.started_at)}</dd>
                </div>
                <div>
                  <dt className="inline">Completed </dt>
                  <dd className="inline">
                    {formatTimestamp(item.completed_at)}
                  </dd>
                </div>
              </dl>
              {item.error ? (
                <p className="text-danger-text text-xs">{item.error}</p>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
