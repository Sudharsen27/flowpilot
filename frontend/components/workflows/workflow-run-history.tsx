"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { RelativeTime } from "@/components/ui/relative-time";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  workflowRunStatusBadge,
  workflowRunStatusLabels,
} from "@/components/workflows/workflow-labels";
import { listWorkflowRuns } from "@/lib/api/workflows";
import type { WorkflowRunListResponse } from "@/types/api";

export function WorkflowRunHistory({
  ruleId,
  ruleName,
}: {
  ruleId: string;
  ruleName: string;
}) {
  const [data, setData] = useState<WorkflowRunListResponse | null>(null);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void listWorkflowRuns(ruleId)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setError(false);
        }
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [ruleId, reloadKey]);

  if (error) {
    return (
      <div className="flex items-center gap-3 text-sm">
        <p className="text-danger-text" role="alert">
          Run history could not be loaded.
        </p>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setReloadKey((v) => v + 1)}
        >
          Retry
        </Button>
      </div>
    );
  }
  if (!data) {
    return (
      <div role="status">
        <Skeleton className="h-16 w-full" />
        <span className="sr-only">Loading run history</span>
      </div>
    );
  }
  if (data.items.length === 0) {
    return (
      <p className="text-muted-foreground text-sm">
        No runs yet. Runs appear here after the trigger happens while this
        workflow is on.
      </p>
    );
  }
  return (
    <ul
      className="divide-border grid divide-y text-sm"
      aria-label={`Recent runs of ${ruleName}`}
    >
      {data.items.map((run) => (
        <li
          key={run.id}
          className="flex flex-wrap items-center justify-between gap-2 py-2"
        >
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <StatusBadge
              status={workflowRunStatusBadge[run.status]}
              label={workflowRunStatusLabels[run.status]}
            />
            <Link
              href={`/leads/${run.lead_id}`}
              className="font-medium underline-offset-4 hover:underline"
            >
              {run.lead_name ?? "Lead"}
            </Link>
            {run.detail ? (
              <span className="text-muted-foreground">{run.detail}</span>
            ) : null}
          </div>
          <span className="text-muted-foreground text-xs">
            <RelativeTime value={run.completed_at ?? run.created_at} />
          </span>
        </li>
      ))}
    </ul>
  );
}
