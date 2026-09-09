"use client";

import { useEffect, useState } from "react";

import { AgentExecutionDetailPanel } from "@/components/agents/agent-execution-detail";
import { AgentExecutionHistoryItem } from "@/components/agents/agent-execution-history-item";
import { historyErrorMessage } from "@/components/agents/execution-status";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listAgentExecutions } from "@/lib/api/agents";
import type { AgentExecutionListItem } from "@/types/api";

export const EXECUTION_HISTORY_PAGE_SIZE = 20;

type AgentExecutionHistoryProps = {
  agentId: string;
};

export function AgentExecutionHistory({ agentId }: AgentExecutionHistoryProps) {
  const [items, setItems] = useState<AgentExecutionListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(EXECUTION_HISTORY_PAGE_SIZE);
  const [offset, setOffset] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listAgentExecutions(agentId, {
      limit: EXECUTION_HISTORY_PAGE_SIZE,
      offset,
    })
      .then((page) => {
        if (cancelled) return;
        setItems(page.items);
        setTotal(page.total);
        setLimit(page.limit);
        setError(null);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setItems([]);
        setError(
          historyErrorMessage(
            cause,
            "Execution history could not be loaded. Please try again.",
            "This agent could not be found.",
          ),
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, offset, retryKey]);

  const pageLimit = limit || EXECUTION_HISTORY_PAGE_SIZE;
  const rangeStart = total === 0 ? 0 : offset + 1;
  const rangeEnd = Math.min(offset + items.length, total);
  const canPrevious = offset > 0;
  const canNext = offset + pageLimit < total;

  function goToOffset(nextOffset: number) {
    setIsLoading(true);
    setError(null);
    setSelectedId(null);
    setOffset(nextOffset);
  }

  return (
    <Card as="section" aria-labelledby="execution-history-title">
      <CardHeader>
        <CardTitle id="execution-history-title">Execution history</CardTitle>
        <CardDescription>
          Recorded runs for this agent. Open a run to inspect the stored input,
          output, and tool activity.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid min-w-0 gap-4">
        {error ? (
          <div className="grid gap-2">
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setIsLoading(true);
                setError(null);
                setRetryKey((key) => key + 1);
              }}
            >
              Retry history
            </Button>
          </div>
        ) : isLoading ? (
          <div role="status" className="grid gap-2">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
            <span className="sr-only">Loading execution history</span>
          </div>
        ) : items.length === 0 ? (
          <p className="text-muted-foreground text-sm leading-6">
            No executions have been recorded for this agent yet. Use Run agent
            above to create the first recorded run.
          </p>
        ) : (
          <>
            <ul className="grid gap-3" aria-label="Recorded executions">
              {items.map((item) => (
                <AgentExecutionHistoryItem
                  key={item.id}
                  item={item}
                  selected={selectedId === item.id}
                  onSelect={setSelectedId}
                />
              ))}
            </ul>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-muted-foreground text-sm" aria-live="polite">
                Showing {rangeStart}–{rangeEnd} of {total}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={!canPrevious}
                  aria-label="Previous executions page"
                  onClick={() =>
                    goToOffset(Math.max(0, offset - pageLimit))
                  }
                >
                  Previous
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={!canNext}
                  aria-label="Next executions page"
                  onClick={() => goToOffset(offset + pageLimit)}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
        {selectedId ? (
          <AgentExecutionDetailPanel
            key={selectedId}
            agentId={agentId}
            executionId={selectedId}
            onClose={() => setSelectedId(null)}
          />
        ) : null}
      </CardContent>
    </Card>
  );
}
