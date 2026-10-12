"use client";

import { ChevronDown, ChevronUp, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import { leadSourceLabels } from "@/components/analytics/analytics-toolbar";
import { Switch } from "@/components/forms/switch";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { RelativeTime } from "@/components/ui/relative-time";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  describeWorkflow,
  workflowTriggerLabels,
} from "@/components/workflows/workflow-labels";
import { WorkflowRunHistory } from "@/components/workflows/workflow-run-history";
import type { WorkflowRule } from "@/types/api";

type WorkflowRuleListProps = {
  rules: readonly WorkflowRule[];
  canManage: boolean;
  busyRuleId: string | null;
  onToggle: (rule: WorkflowRule) => void;
  onEdit: (rule: WorkflowRule) => void;
  onDelete: (rule: WorkflowRule) => void;
};

export function WorkflowRuleList({
  rules,
  canManage,
  busyRuleId,
  onToggle,
  onEdit,
  onDelete,
}: WorkflowRuleListProps) {
  const [openHistory, setOpenHistory] = useState<string | null>(null);

  return (
    <ul className="grid gap-3" aria-label="Workflows">
      {rules.map((rule) => {
        const busy = busyRuleId === rule.id;
        const historyOpen = openHistory === rule.id;
        const counts = rule.run_counts;
        const totalRuns =
          counts.pending + counts.succeeded + counts.skipped + counts.failed;
        return (
          <li key={rule.id}>
            <Card as="article" aria-labelledby={`workflow-${rule.id}-name`}>
              <CardContent className="grid gap-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="grid min-w-0 gap-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge
                        status={rule.enabled ? "active" : "paused"}
                        label={rule.enabled ? "On" : "Off"}
                      />
                      {counts.failed > 0 ? (
                        <StatusBadge
                          status="failed"
                          label={`${counts.failed} failed`}
                        />
                      ) : null}
                      {counts.pending > 0 ? (
                        <StatusBadge
                          status="pending"
                          label={`${counts.pending} waiting`}
                        />
                      ) : null}
                    </div>
                    <h3
                      id={`workflow-${rule.id}-name`}
                      className="text-base font-medium tracking-tight break-words"
                    >
                      {rule.name}
                    </h3>
                    <p className="text-muted-foreground text-sm">
                      <span className="text-foreground font-medium">When</span>{" "}
                      {workflowTriggerLabels[rule.trigger].toLowerCase()}
                      {rule.source_filter
                        ? ` from ${leadSourceLabels[rule.source_filter]}`
                        : ""}
                      ,{" "}
                      <span className="text-foreground font-medium">then</span>{" "}
                      {describeWorkflow(rule).toLowerCase()}.
                    </p>
                  </div>
                  {canManage ? (
                    <div className="flex items-center gap-2">
                      <label
                        htmlFor={`workflow-${rule.id}-enabled`}
                        className="text-sm"
                      >
                        {rule.enabled ? "On" : "Off"}
                      </label>
                      <Switch
                        id={`workflow-${rule.id}-enabled`}
                        checked={rule.enabled}
                        disabled={busy}
                        onCheckedChange={() => onToggle(rule)}
                        aria-label={`${rule.enabled ? "Turn off" : "Turn on"} ${rule.name}`}
                      />
                    </div>
                  ) : null}
                </div>
                <p className="text-muted-foreground text-xs">
                  {totalRuns === 0 ? (
                    "Has not run yet."
                  ) : (
                    <>
                      {counts.succeeded} done · {counts.skipped} skipped ·{" "}
                      {counts.failed} failed
                      {rule.last_run_at ? (
                        <>
                          {" "}
                          · last run <RelativeTime value={rule.last_run_at} />
                        </>
                      ) : null}
                    </>
                  )}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    aria-expanded={historyOpen}
                    aria-controls={`workflow-${rule.id}-history`}
                    onClick={() => setOpenHistory(historyOpen ? null : rule.id)}
                  >
                    {historyOpen ? (
                      <ChevronUp aria-hidden="true" />
                    ) : (
                      <ChevronDown aria-hidden="true" />
                    )}
                    {historyOpen ? "Hide runs" : "Show runs"}
                  </Button>
                  {canManage ? (
                    <>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => onEdit(rule)}
                        aria-label={`Edit ${rule.name}`}
                      >
                        <Pencil aria-hidden="true" />
                        Edit
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={busy}
                        onClick={() => onDelete(rule)}
                        aria-label={`Delete ${rule.name}`}
                      >
                        <Trash2 aria-hidden="true" />
                        Delete
                      </Button>
                    </>
                  ) : null}
                </div>
                {historyOpen ? (
                  <div id={`workflow-${rule.id}-history`}>
                    <WorkflowRunHistory ruleId={rule.id} ruleName={rule.name} />
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}
