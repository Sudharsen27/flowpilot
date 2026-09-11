"use client";

import { useEffect, useState } from "react";

import { SalesRunStatusBadge } from "@/components/agents/sales-run-status-badge";
import { StartSalesRunDialog } from "@/components/agents/start-sales-run-dialog";
import { AiBadge } from "@/components/ai/ai-badge";
import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { StatePanel } from "@/components/data-display/state-panel";
import { DraftLeadResponseDialog } from "@/components/leads/draft-lead-response-dialog";
import { SectionHeader } from "@/components/layout/section-header";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { formatTimestamp } from "@/components/agents/execution-status";
import { ApiError } from "@/lib/api/client";
import { getLead } from "@/lib/api/leads";
import { cancelSalesRun, listSalesRuns } from "@/lib/api/sales-runs";
import type { Lead, SalesRun } from "@/types/api";

const stageLabels: Record<SalesRun["stage"], string> = {
  MATCH_LEAD: "Match lead",
  QUALIFY: "Qualify",
  DRAFT: "Draft",
  AWAIT_APPROVAL: "Await approval",
};

type SalesRunsPanelProps = {
  agentId: string;
  canStart: boolean;
};

function listError(cause: unknown) {
  if (cause instanceof ApiError && cause.status === 401) {
    return "Your session has expired. Sign in again to view sales runs.";
  }
  return "Sales runs could not be loaded.";
}

export function SalesRunsPanel({ agentId, canStart }: SalesRunsPanelProps) {
  const [items, setItems] = useState<SalesRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startOpen, setStartOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [review, setReview] = useState<{ lead: Lead; draftId: string } | null>(
    null,
  );
  const [cancelTarget, setCancelTarget] = useState<SalesRun | null>(null);
  const [cancelPending, setCancelPending] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listSalesRuns(agentId)
      .then((page) => {
        if (!cancelled) setItems(page.items);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(listError(cause));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentId, refreshKey]);

  async function openReview(run: SalesRun) {
    if (!run.response_draft_id) return;
    const lead = await getLead(run.lead_id);
    setReview({ lead, draftId: run.response_draft_id });
  }

  async function confirmCancel() {
    if (!cancelTarget || cancelPending) return;
    setCancelPending(true);
    setCancelError(null);
    try {
      await cancelSalesRun(agentId, cancelTarget.id, {
        expected_revision: cancelTarget.revision,
      });
      setCancelTarget(null);
      setLoading(true);
      setRefreshKey((value) => value + 1);
    } catch (cause) {
      setCancelError(
        cause instanceof ApiError && typeof (cause.body as { detail?: string })?.detail === "string"
          ? (cause.body as { detail: string }).detail
          : "The sales run could not be cancelled.",
      );
    } finally {
      setCancelPending(false);
    }
  }

  const columns: DataTableColumn<SalesRun>[] = [
    {
      key: "lead",
      header: "Lead",
      cell: (row) => row.lead?.name ?? row.lead_id,
    },
    {
      key: "stage",
      header: "Stage",
      cell: (row) => stageLabels[row.stage],
    },
    {
      key: "status",
      header: "Status",
      cell: (row) => (
        <span className="inline-flex items-center gap-2">
          <SalesRunStatusBadge status={row.status} />
          {row.status === "RUNNING" ? <AiBadge label="Processing" /> : null}
        </span>
      ),
    },
    {
      key: "created",
      header: "Created",
      cell: (row) => formatTimestamp(row.created_at) ?? "—",
    },
    {
      key: "updated",
      header: "Updated",
      cell: (row) => formatTimestamp(row.updated_at) ?? "—",
    },
  ];

  return (
    <section aria-label="Sales runs" className="grid gap-4">
      <SectionHeader
        title="Sales runs"
        description="Qualify an enquiry and prepare a response for human review. This is not the generic agent debugger, and it does not send email."
        action={
          canStart ? (
            <Button type="button" onClick={() => setStartOpen(true)}>
              Start sales run
            </Button>
          ) : null
        }
      />
      {error ? (
        <StatePanel
          kind="error"
          className="max-w-none"
          title="Sales runs could not be loaded"
          description={error}
          action={
            <Button type="button" variant="outline" onClick={() => {
              setLoading(true);
              setError(null);
              setRefreshKey((value) => value + 1);
            }}>
              Retry
            </Button>
          }
        />
      ) : (
        <DataTable
          columns={columns}
          rows={items}
          getRowKey={(row) => row.id}
          loading={loading}
          emptyTitle="No sales runs yet"
          emptyDescription="Start a sales run to qualify an enquiry and draft a response for review."
          rowActions={(row) => (
            <div className="flex flex-wrap gap-2">
              {row.status === "WAITING_APPROVAL" && row.response_draft_id ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => void openReview(row)}
                >
                  Review draft
                </Button>
              ) : null}
              {row.status === "FAILED" && row.error ? (
                <span className="text-danger-text max-w-48 text-xs">{row.error}</span>
              ) : null}
              {row.status === "RUNNING" || row.status === "WAITING_APPROVAL" ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setCancelError(null);
                    setCancelTarget(row);
                  }}
                >
                  Cancel run
                </Button>
              ) : null}
            </div>
          )}
        />
      )}
      <StartSalesRunDialog
        open={startOpen}
        agentId={agentId}
        onOpenChange={setStartOpen}
        onCompleted={() => {
          setLoading(true);
          setRefreshKey((value) => value + 1);
        }}
      />
      <DraftLeadResponseDialog
        open={review !== null}
        lead={review?.lead ?? null}
        draftId={review?.draftId}
        onOpenChange={(next) => {
          if (!next) setReview(null);
        }}
        onCompleted={() => {
          setLoading(true);
          setRefreshKey((value) => value + 1);
        }}
      />
      <ConfirmDialog
        open={cancelTarget !== null}
        onOpenChange={(next) => {
          if (!next && !cancelPending) setCancelTarget(null);
        }}
        title="Cancel sales run"
        description="This stops the sales run. It does not reject the draft or change the lead's CRM status."
        confirmLabel={cancelPending ? "Cancelling…" : "Cancel run"}
        variant="destructive"
        confirmPending={cancelPending}
        onConfirm={() => void confirmCancel()}
      >
        {cancelError ? (
          <p className="text-danger-text text-sm" role="alert">
            {cancelError}
          </p>
        ) : null}
      </ConfirmDialog>
    </section>
  );
}
