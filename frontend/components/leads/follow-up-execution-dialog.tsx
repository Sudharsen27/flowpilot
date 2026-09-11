"use client";

import { useEffect, useState } from "react";

import {
  FollowUpExecutionStatusBadge,
} from "@/components/leads/follow-up-status-badge";
import {
  formatDuration,
  formatFailureCategory,
  formatTimestamp,
  historyErrorMessage,
} from "@/components/agents/execution-status";
import {
  Dialog,
  DialogCancel,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { getLeadFollowUpExecutions } from "@/lib/api/leads";
import type { FollowUpOperationsItem, LeadFollowUpExecution } from "@/types/api";

type FollowUpExecutionDialogProps = {
  open: boolean;
  item: FollowUpOperationsItem | null;
  onOpenChange: (open: boolean) => void;
};

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] gap-3">
      <dt className="text-muted-foreground text-xs font-medium">{label}</dt>
      <dd className="min-w-0 text-sm break-words">{value}</dd>
    </div>
  );
}

function ExecutionCard({ execution }: { execution: LeadFollowUpExecution }) {
  const duration = formatDuration(execution.duration_ms);
  const category = formatFailureCategory(execution.failure_category);
  const started = formatTimestamp(execution.started_at);
  const completed = formatTimestamp(execution.completed_at);
  return (
    <li className="border-border rounded-md border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Attempt {execution.attempt}</h3>
        <FollowUpExecutionStatusBadge status={execution.status} />
      </div>
      <dl className="mt-3 grid gap-2">
        <Field label="Recipient" value={execution.recipient_email} />
        <Field label="Provider" value={execution.provider ?? "Not recorded"} />
        <Field
          label="Provider message ID"
          value={execution.provider_message_id ?? "Not recorded"}
        />
        <Field label="Started" value={started ?? "Not started"} />
        <Field label="Completed" value={completed ?? "Not completed"} />
        <Field label="Duration" value={duration ?? "Not available"} />
        {category ? <Field label="Failure category" value={category} /> : null}
        {execution.error ? <Field label="Error" value={execution.error} /> : null}
      </dl>
    </li>
  );
}

/**
 * Read-only attempt history for one follow-up. Opening it never sends email.
 * Only safe fields are shown: no provider payload and no secrets.
 */
export function FollowUpExecutionDialog({
  open,
  item,
  onOpenChange,
}: FollowUpExecutionDialogProps) {
  const [executions, setExecutions] = useState<LeadFollowUpExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !item) return;
    let cancelled = false;
    void getLeadFollowUpExecutions(item.lead.id, item.follow_up.id)
      .then((page) => {
        if (!cancelled) setExecutions(page.items);
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(
            historyErrorMessage(
              cause,
              "This delivery history could not be loaded. Try again.",
              "This follow-up could not be found.",
            ),
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [item, open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Delivery history</DialogTitle>
          <DialogDescription>
            {item
              ? `Send attempts for the follow-up on ${item.lead.name}. Attempts are recorded by the follow-up worker.`
              : "Send attempts recorded for this follow-up."}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="grid gap-3" role="status">
            <Skeleton className="h-24 w-full" />
            <span className="sr-only">Loading delivery history</span>
          </div>
        ) : error ? (
          <p role="alert" className="text-danger-text text-sm">
            {error}
          </p>
        ) : executions.length === 0 ? (
          <div className="border-border rounded-md border border-dashed p-5">
            <h3 className="text-sm font-medium">No send attempts yet</h3>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              Nothing has been emailed for this follow-up. Email follow-ups are
              sent by the follow-up worker once they are due.
            </p>
          </div>
        ) : (
          <ul className="grid gap-3">
            {executions.map((execution) => (
              <ExecutionCard key={execution.id} execution={execution} />
            ))}
          </ul>
        )}

        <DialogFooter>
          <DialogCancel>Close</DialogCancel>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
