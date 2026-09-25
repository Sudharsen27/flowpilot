"use client";

import { useEffect, useState } from "react";

import { formatTimestamp } from "@/components/agents/execution-status";
import { SalesRunStatusBadge } from "@/components/agents/sales-run-status-badge";
import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { DetailRow } from "@/components/data-display/detail-row";
import { StatePanel } from "@/components/data-display/state-panel";
import { DraftLeadResponseDialog } from "@/components/leads/draft-lead-response-dialog";
import {
  FollowUpStatusBadge,
  followUpTypeLabel,
} from "@/components/leads/follow-up-status-badge";
import { LeadFollowUpsDialog } from "@/components/leads/lead-follow-ups-dialog";
import { SectionHeader } from "@/components/layout/section-header";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ApiError } from "@/lib/api/client";
import { getFollowUpOperations, getLead, getLeadResponseDraft } from "@/lib/api/leads";
import { cancelSalesRun, listOrganizationSalesRuns, sendSalesRun } from "@/lib/api/sales-runs";
import type {
  FollowUpOperationsItem,
  Lead,
  LeadResponseDraftResult,
  LeadResponseReviewStatus,
  SalesRun,
} from "@/types/api";

const PAGE_SIZE = 20;
const EMAIL_SUBJECT = "Re: Your enquiry";

const reviewLabels: Record<LeadResponseReviewStatus, string> = {
  GENERATED: "Generated",
  EDITED: "Edited",
  APPROVED: "Approved",
  REJECTED: "Rejected",
};

type NeedsAttentionProps = {
  onChanged?: () => void;
};

type QueuePage<T> = {
  items: T[];
  total: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function listError(cause: unknown, fallback: string) {
  if (cause instanceof ApiError && cause.status === 401) {
    return "Your session has expired. Sign in again to view this queue.";
  }
  return fallback;
}

function actionError(cause: unknown, fallback: string) {
  if (cause instanceof ApiError && isRecord(cause.body) && typeof cause.body.detail === "string") {
    return cause.body.detail;
  }
  return fallback;
}

function draftIsApproved(row: SalesRun) {
  return row.response_draft?.review_status === "APPROVED";
}

function canSendApprovedResponse(row: SalesRun) {
  if (!draftIsApproved(row)) return false;
  if (row.status === "WAITING_APPROVAL") return true;
  return row.status === "FAILED" && row.stage === "SEND";
}

function failureCopy(row: SalesRun) {
  const message = row.email_send?.error ?? row.error;
  if (!message) return "The approved email was not sent.";
  return message;
}

function leadCell(name: string, email: string | null | undefined) {
  return (
    <div className="min-w-0">
      <p className="truncate font-medium">{name}</p>
      <p className="text-muted-foreground truncate text-xs">{email || "—"}</p>
    </div>
  );
}

function QueuePagination({
  total,
  offset,
  loading,
  onPrevious,
  onNext,
}: {
  total: number;
  offset: number;
  loading: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  if (total === 0) return null;
  const start = offset + 1;
  const end = Math.min(offset + PAGE_SIZE, total);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <p className="text-muted-foreground text-sm">
        Showing {start}–{end} of {total}
      </p>
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={offset === 0 || loading}
          onClick={onPrevious}
        >
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={offset + PAGE_SIZE >= total || loading}
          onClick={onNext}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

export function NeedsAttention({ onChanged }: NeedsAttentionProps) {
  const [waitingOffset, setWaitingOffset] = useState(0);
  const [waitingKey, setWaitingKey] = useState(0);
  const [waitingLoading, setWaitingLoading] = useState(true);
  const [waitingError, setWaitingError] = useState<string | null>(null);
  const [waiting, setWaiting] = useState<QueuePage<SalesRun>>({ items: [], total: 0 });

  const [failedOffset, setFailedOffset] = useState(0);
  const [failedKey, setFailedKey] = useState(0);
  const [failedLoading, setFailedLoading] = useState(true);
  const [failedError, setFailedError] = useState<string | null>(null);
  const [failed, setFailed] = useState<QueuePage<SalesRun>>({ items: [], total: 0 });

  const [overdueOffset, setOverdueOffset] = useState(0);
  const [overdueKey, setOverdueKey] = useState(0);
  const [overdueLoading, setOverdueLoading] = useState(true);
  const [overdueError, setOverdueError] = useState<string | null>(null);
  const [overdue, setOverdue] = useState<QueuePage<FollowUpOperationsItem>>({
    items: [],
    total: 0,
  });

  const [review, setReview] = useState<{ lead: Lead; draftId: string } | null>(null);
  const [cancelTarget, setCancelTarget] = useState<SalesRun | null>(null);
  const [cancelPending, setCancelPending] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [sendTarget, setSendTarget] = useState<SalesRun | null>(null);
  const [sendDraft, setSendDraft] = useState<LeadResponseDraftResult | null>(null);
  const [sendPending, setSendPending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [manageLead, setManageLead] = useState<Lead | null>(null);
  const [manageOpen, setManageOpen] = useState(false);
  const [manageKey, setManageKey] = useState(0);
  const [actionAlert, setActionAlert] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listOrganizationSalesRuns({
      status: "WAITING_APPROVAL",
      limit: PAGE_SIZE,
      offset: waitingOffset,
    })
      .then((page) => {
        if (cancelled) return;
        if (page.items.length === 0 && waitingOffset > 0) {
          setWaitingOffset(Math.max(0, waitingOffset - PAGE_SIZE));
          return;
        }
        setWaiting({ items: page.items, total: page.total });
        setWaitingError(null);
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setWaitingError(listError(cause, "Waiting for review could not be loaded."));
          setWaiting({ items: [], total: 0 });
        }
      })
      .finally(() => {
        if (!cancelled) setWaitingLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [waitingOffset, waitingKey]);

  useEffect(() => {
    let cancelled = false;
    void listOrganizationSalesRuns({
      status: "FAILED",
      stage: "SEND",
      limit: PAGE_SIZE,
      offset: failedOffset,
    })
      .then((page) => {
        if (cancelled) return;
        if (page.items.length === 0 && failedOffset > 0) {
          setFailedOffset(Math.max(0, failedOffset - PAGE_SIZE));
          return;
        }
        setFailed({ items: page.items, total: page.total });
        setFailedError(null);
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setFailedError(listError(cause, "Failed sends could not be loaded."));
          setFailed({ items: [], total: 0 });
        }
      })
      .finally(() => {
        if (!cancelled) setFailedLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [failedOffset, failedKey]);

  useEffect(() => {
    let cancelled = false;
    void getFollowUpOperations({
      overdue: true,
      limit: PAGE_SIZE,
      offset: overdueOffset,
    })
      .then((page) => {
        if (cancelled) return;
        if (page.items.length === 0 && overdueOffset > 0) {
          setOverdueOffset(Math.max(0, overdueOffset - PAGE_SIZE));
          return;
        }
        setOverdue({ items: page.items, total: page.total });
        setOverdueError(null);
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setOverdueError(listError(cause, "Overdue follow-ups could not be loaded."));
          setOverdue({ items: [], total: 0 });
        }
      })
      .finally(() => {
        if (!cancelled) setOverdueLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [overdueOffset, overdueKey]);

  function refreshQueues() {
    setWaitingLoading(true);
    setFailedLoading(true);
    setOverdueLoading(true);
    setWaitingError(null);
    setFailedError(null);
    setOverdueError(null);
    setWaitingKey((value) => value + 1);
    setFailedKey((value) => value + 1);
    setOverdueKey((value) => value + 1);
    onChanged?.();
  }

  function refreshWaiting() {
    setWaitingLoading(true);
    setWaitingError(null);
    setWaitingKey((value) => value + 1);
    onChanged?.();
  }

  function refreshFailed() {
    setFailedLoading(true);
    setFailedError(null);
    setFailedKey((value) => value + 1);
    onChanged?.();
  }

  function refreshOverdue() {
    setOverdueLoading(true);
    setOverdueError(null);
    setOverdueKey((value) => value + 1);
    onChanged?.();
  }

  async function openReview(run: SalesRun) {
    if (!run.response_draft_id) return;
    setActionAlert(null);
    try {
      const lead = await getLead(run.lead_id);
      setReview({ lead, draftId: run.response_draft_id });
    } catch (cause) {
      setActionAlert(actionError(cause, "The draft could not be opened."));
    }
  }

  async function openSend(run: SalesRun) {
    if (!run.response_draft_id || sendPending) return;
    setSendError(null);
    setSendDraft(null);
    setSendTarget(run);
    setActionAlert(null);
    try {
      const draft = await getLeadResponseDraft(run.lead_id, run.response_draft_id);
      setSendDraft(draft);
    } catch (cause) {
      setSendError(actionError(cause, "The approved response could not be loaded."));
    }
  }

  async function confirmSend() {
    if (!sendTarget || sendPending) return;
    setSendPending(true);
    setSendError(null);
    try {
      const result = await sendSalesRun(sendTarget.agent_id, sendTarget.id, {
        expected_revision: sendTarget.revision,
      });
      refreshQueues();
      if (result.status === "FAILED") {
        setSendError(result.error ?? "The email could not be sent.");
        return;
      }
      setSendTarget(null);
      setSendDraft(null);
    } catch (cause) {
      setSendError(actionError(cause, "The approved response could not be sent."));
    } finally {
      setSendPending(false);
    }
  }

  async function confirmCancel() {
    if (!cancelTarget || cancelPending) return;
    setCancelPending(true);
    setCancelError(null);
    try {
      await cancelSalesRun(cancelTarget.agent_id, cancelTarget.id, {
        expected_revision: cancelTarget.revision,
      });
      setCancelTarget(null);
      refreshWaiting();
    } catch (cause) {
      setCancelError(actionError(cause, "The sales run could not be cancelled."));
    } finally {
      setCancelPending(false);
    }
  }

  async function openManage(item: FollowUpOperationsItem) {
    setActionAlert(null);
    try {
      const lead = await getLead(item.lead.id);
      setManageLead(lead);
      setManageKey((value) => value + 1);
      setManageOpen(true);
    } catch (cause) {
      setActionAlert(actionError(cause, "This follow-up could not be opened."));
    }
  }

  const waitingColumns: DataTableColumn<SalesRun>[] = [
    {
      key: "lead",
      header: "Lead",
      cell: (row) => leadCell(row.lead?.name ?? row.lead_id, row.lead?.email),
    },
    {
      key: "review",
      header: "Review status",
      cell: (row) =>
        row.response_draft?.review_status
          ? reviewLabels[row.response_draft.review_status]
          : "—",
    },
    {
      key: "status",
      header: "Status",
      cell: (row) => <SalesRunStatusBadge status={row.status} />,
    },
    {
      key: "updated",
      header: "Updated",
      cell: (row) => formatTimestamp(row.updated_at) ?? "—",
    },
  ];

  const failedColumns: DataTableColumn<SalesRun>[] = [
    {
      key: "lead",
      header: "Lead",
      cell: (row) => leadCell(row.lead?.name ?? row.lead_id, row.lead?.email),
    },
    {
      key: "failed",
      header: "What failed",
      cell: (row) => (
        <p className="text-danger-text line-clamp-2 text-sm">{failureCopy(row)}</p>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (row) => <SalesRunStatusBadge status={row.status} />,
    },
    {
      key: "updated",
      header: "Updated",
      cell: (row) => formatTimestamp(row.updated_at) ?? "—",
    },
  ];

  const overdueColumns: DataTableColumn<FollowUpOperationsItem>[] = [
    {
      key: "lead",
      header: "Lead",
      cell: (item) => leadCell(item.lead.name, item.lead.email),
    },
    {
      key: "due",
      header: "Due",
      cell: (item) => formatTimestamp(item.follow_up.due_at) ?? "—",
    },
    {
      key: "type",
      header: "Type",
      cell: (item) => followUpTypeLabel(item.follow_up.type),
    },
    {
      key: "status",
      header: "Status",
      cell: (item) => <FollowUpStatusBadge followUp={item.follow_up} />,
    },
  ];

  return (
    <section className="grid gap-5" aria-label="Needs attention">
      <SectionHeader
        title="Needs attention"
        description="Drafts waiting for review, emails that failed to send, and overdue follow-ups. Completed work is not listed here."
      />
      {actionAlert ? (
        <p className="text-danger-text text-sm" role="alert">
          {actionAlert}
        </p>
      ) : null}

      <section
        className="border-warning/40 grid gap-4 border-l-2 pl-4 sm:pl-5"
        aria-labelledby="waiting-review-heading"
      >
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h3 id="waiting-review-heading" className="text-sm font-medium">
            Waiting for review
          </h3>
          {!waitingLoading && !waitingError ? (
            <p className="text-muted-foreground text-sm">
              {waiting.total} waiting
            </p>
          ) : null}
        </div>
        {waitingError ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            title="Waiting for review could not be loaded"
            description={waitingError}
            action={
              <Button type="button" variant="outline" onClick={refreshWaiting}>
                Retry
              </Button>
            }
          />
        ) : (
          <>
            <DataTable
              className="max-w-none"
              columns={waitingColumns}
              rows={waiting.items}
              getRowKey={(row) => row.id}
              loading={waitingLoading}
              emptyTitle="Nothing waiting for review"
              emptyDescription="When a sales run has a draft ready, it will appear here for a person to review. Approval does not send the email."
              rowActions={(row) => (
                <div className="flex flex-wrap gap-2">
                  {row.response_draft_id ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void openReview(row)}
                    >
                      Review draft
                    </Button>
                  ) : null}
                  {canSendApprovedResponse(row) ? (
                    <Button
                      type="button"
                      size="sm"
                      disabled={sendPending && sendTarget?.id === row.id}
                      onClick={() => void openSend(row)}
                    >
                      Send approved response
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={cancelPending && cancelTarget?.id === row.id}
                    onClick={() => {
                      setCancelError(null);
                      setCancelTarget(row);
                    }}
                  >
                    Cancel run
                  </Button>
                </div>
              )}
            />
            <QueuePagination
              total={waiting.total}
              offset={waitingOffset}
              loading={waitingLoading}
              onPrevious={() => {
                setWaitingLoading(true);
                setWaitingOffset(Math.max(0, waitingOffset - PAGE_SIZE));
              }}
              onNext={() => {
                setWaitingLoading(true);
                setWaitingOffset(waitingOffset + PAGE_SIZE);
              }}
            />
          </>
        )}
      </section>

      <section
        className="border-destructive/40 grid gap-4 border-l-2 pl-4 sm:pl-5"
        aria-labelledby="failed-sends-heading"
      >
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h3 id="failed-sends-heading" className="text-sm font-medium">
            Failed sends
          </h3>
          {!failedLoading && !failedError ? (
            <p className="text-muted-foreground text-sm">{failed.total} failed</p>
          ) : null}
        </div>
        {failedError ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            title="Failed sends could not be loaded"
            description={failedError}
            action={
              <Button type="button" variant="outline" onClick={refreshFailed}>
                Retry
              </Button>
            }
          />
        ) : (
          <>
            <DataTable
              className="max-w-none"
              columns={failedColumns}
              rows={failed.items}
              getRowKey={(row) => row.id}
              loading={failedLoading}
              emptyTitle="No failed sends"
              emptyDescription="Approved emails that the provider did not accept will appear here so you can retry."
              rowActions={(row) => (
                <div className="flex flex-wrap gap-2">
                  {row.response_draft_id ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => void openReview(row)}
                    >
                      Review draft
                    </Button>
                  ) : null}
                  {canSendApprovedResponse(row) ? (
                    <Button
                      type="button"
                      size="sm"
                      disabled={sendPending && sendTarget?.id === row.id}
                      onClick={() => void openSend(row)}
                    >
                      Retry send
                    </Button>
                  ) : null}
                </div>
              )}
            />
            <QueuePagination
              total={failed.total}
              offset={failedOffset}
              loading={failedLoading}
              onPrevious={() => {
                setFailedLoading(true);
                setFailedOffset(Math.max(0, failedOffset - PAGE_SIZE));
              }}
              onNext={() => {
                setFailedLoading(true);
                setFailedOffset(failedOffset + PAGE_SIZE);
              }}
            />
          </>
        )}
      </section>

      <section
        className="border-warning/40 grid gap-4 border-l-2 pl-4 sm:pl-5"
        aria-labelledby="overdue-follow-ups-heading"
      >
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h3 id="overdue-follow-ups-heading" className="text-sm font-medium">
            Overdue follow-ups
          </h3>
          {!overdueLoading && !overdueError ? (
            <p className="text-muted-foreground text-sm">{overdue.total} overdue</p>
          ) : null}
        </div>
        {overdueError ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            title="Overdue follow-ups could not be loaded"
            description={overdueError}
            action={
              <Button type="button" variant="outline" onClick={refreshOverdue}>
                Retry
              </Button>
            }
          />
        ) : (
          <>
            <DataTable
              className="max-w-none"
              columns={overdueColumns}
              rows={overdue.items}
              getRowKey={(item) => item.follow_up.id}
              loading={overdueLoading}
              emptyTitle="No overdue follow-ups"
              emptyDescription="Pending follow-ups past their due time will appear here."
              rowActions={(item) => (
                <Button type="button" size="sm" onClick={() => void openManage(item)}>
                  Manage
                </Button>
              )}
            />
            <QueuePagination
              total={overdue.total}
              offset={overdueOffset}
              loading={overdueLoading}
              onPrevious={() => {
                setOverdueLoading(true);
                setOverdueOffset(Math.max(0, overdueOffset - PAGE_SIZE));
              }}
              onNext={() => {
                setOverdueLoading(true);
                setOverdueOffset(overdueOffset + PAGE_SIZE);
              }}
            />
          </>
        )}
      </section>

      <DraftLeadResponseDialog
        open={review !== null}
        lead={review?.lead ?? null}
        draftId={review?.draftId}
        onOpenChange={(next) => {
          if (!next) setReview(null);
        }}
        onCompleted={() => {
          refreshQueues();
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
      <ConfirmDialog
        open={sendTarget !== null}
        onOpenChange={(next) => {
          if (!next && !sendPending) {
            setSendTarget(null);
            setSendDraft(null);
            setSendError(null);
          }
        }}
        title="Send approved response?"
        description="Approval does not send the email. Sending is a separate action. This will send the approved response to the lead. This is an external action."
        confirmLabel={sendPending ? "Sending…" : "Send approved response"}
        confirmPending={sendPending || !sendDraft}
        onConfirm={() => void confirmSend()}
      >
        <dl className="mt-4 grid gap-2">
          <DetailRow
            label="To"
            value={sendTarget?.lead?.email ?? "—"}
            muted={!sendTarget?.lead?.email}
          />
          <DetailRow label="Subject" value={EMAIL_SUBJECT} />
          <DetailRow
            label="Message"
            value={
              <span className="whitespace-pre-wrap">{sendDraft?.response ?? "—"}</span>
            }
          />
        </dl>
        {sendError ? (
          <p className="text-danger-text mt-3 text-sm" role="alert">
            {sendError}
          </p>
        ) : null}
      </ConfirmDialog>
      <LeadFollowUpsDialog
        key={manageKey}
        open={manageOpen}
        lead={manageLead}
        onOpenChange={(open) => {
          setManageOpen(open);
          if (!open) setManageLead(null);
        }}
        onChanged={refreshOverdue}
      />
    </section>
  );
}
