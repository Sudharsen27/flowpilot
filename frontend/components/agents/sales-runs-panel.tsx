"use client";

import { useEffect, useState } from "react";

import { SalesRunStatusBadge } from "@/components/agents/sales-run-status-badge";
import { StartSalesRunDialog } from "@/components/agents/start-sales-run-dialog";
import { AiBadge } from "@/components/ai/ai-badge";
import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { DetailRow } from "@/components/data-display/detail-row";
import { StatePanel } from "@/components/data-display/state-panel";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import { DraftLeadResponseDialog } from "@/components/leads/draft-lead-response-dialog";
import { FollowUpStatusBadge } from "@/components/leads/follow-up-status-badge";
import { SectionHeader } from "@/components/layout/section-header";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogCancel,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatTimestamp } from "@/components/agents/execution-status";
import { ApiError } from "@/lib/api/client";
import { getLead, getLeadResponseDraft } from "@/lib/api/leads";
import {
  cancelSalesRun,
  listSalesRuns,
  scheduleSalesRunFollowUp,
  sendSalesRun,
} from "@/lib/api/sales-runs";
import type {
  Lead,
  LeadFollowUp,
  LeadFollowUpType,
  LeadResponseDraftResult,
  SalesRun,
  SalesRunFollowUpSummary,
} from "@/types/api";

const EMAIL_SUBJECT = "Re: Your enquiry";

const stageLabels: Record<SalesRun["stage"], string> = {
  MATCH_LEAD: "Match lead",
  QUALIFY: "Qualify",
  DRAFT: "Draft",
  AWAIT_APPROVAL: "Await approval",
  SEND: "Send",
  DONE: "Done",
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

function actionError(cause: unknown, fallback: string) {
  if (cause instanceof ApiError && isRecord(cause.body) && typeof cause.body.detail === "string") {
    return cause.body.detail;
  }
  return fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function draftIsApproved(row: SalesRun) {
  return row.response_draft?.review_status === "APPROVED";
}

function canSendApprovedResponse(row: SalesRun) {
  if (!draftIsApproved(row)) return false;
  if (row.status === "WAITING_APPROVAL") return true;
  return row.status === "FAILED" && row.stage === "SEND";
}

function canScheduleFollowUp(row: SalesRun) {
  return (
    row.status === "COMPLETED" &&
    row.stage === "DONE" &&
    !row.follow_up_id &&
    !row.follow_up
  );
}

function followUpAsLeadFollowUp(
  summary: SalesRunFollowUpSummary,
  leadId: string,
): LeadFollowUp {
  return {
    id: summary.id,
    lead_id: leadId,
    type: summary.type,
    status: summary.status,
    due_at: summary.due_at,
    revision: 1,
    is_overdue: summary.is_overdue,
    completed_at: null,
    cancelled_at: null,
    created_at: summary.due_at,
    updated_at: summary.due_at,
  };
}

function fromLocalInput(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function followUpTypeLabel(type: LeadFollowUpType) {
  return type === "EMAIL_FOLLOW_UP" ? "Email follow-up" : "Manual follow-up";
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
  const [sendTarget, setSendTarget] = useState<SalesRun | null>(null);
  const [sendDraft, setSendDraft] = useState<LeadResponseDraftResult | null>(null);
  const [sendPending, setSendPending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [scheduleTarget, setScheduleTarget] = useState<SalesRun | null>(null);
  const [scheduleConfirming, setScheduleConfirming] = useState(false);
  const [scheduleType, setScheduleType] = useState<LeadFollowUpType>("EMAIL_FOLLOW_UP");
  const [scheduleDueAt, setScheduleDueAt] = useState("");
  const [scheduleNotes, setScheduleNotes] = useState("");
  const [scheduleBody, setScheduleBody] = useState("");
  const [schedulePending, setSchedulePending] = useState(false);
  const [scheduleError, setScheduleError] = useState<string | null>(null);

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

  async function openSend(run: SalesRun) {
    if (!run.response_draft_id || sendPending) return;
    setSendError(null);
    setSendDraft(null);
    setSendTarget(run);
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
      const result = await sendSalesRun(agentId, sendTarget.id, {
        expected_revision: sendTarget.revision,
      });
      setLoading(true);
      setRefreshKey((value) => value + 1);
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
      await cancelSalesRun(agentId, cancelTarget.id, {
        expected_revision: cancelTarget.revision,
      });
      setCancelTarget(null);
      setLoading(true);
      setRefreshKey((value) => value + 1);
    } catch (cause) {
      setCancelError(actionError(cause, "The sales run could not be cancelled."));
    } finally {
      setCancelPending(false);
    }
  }

  function openSchedule(row: SalesRun) {
    setScheduleError(null);
    setScheduleConfirming(false);
    setScheduleType("EMAIL_FOLLOW_UP");
    setScheduleDueAt("");
    setScheduleNotes("");
    setScheduleBody("");
    setScheduleTarget(row);
  }

  function resetSchedule() {
    setScheduleTarget(null);
    setScheduleConfirming(false);
    setScheduleError(null);
  }

  function schedulePayload() {
    const iso = fromLocalInput(scheduleDueAt);
    return iso;
  }

  const scheduleReady =
    Boolean(schedulePayload()) &&
    (scheduleType === "MANUAL_FOLLOW_UP" || Boolean(scheduleBody.trim()));

  async function confirmSchedule() {
    if (!scheduleTarget || schedulePending) return;
    const iso = schedulePayload();
    if (!iso) {
      setScheduleError("A valid due date and time is required.");
      return;
    }
    if (scheduleType === "EMAIL_FOLLOW_UP" && !scheduleBody.trim()) {
      setScheduleError("Email body is required for email follow-ups.");
      return;
    }
    setSchedulePending(true);
    setScheduleError(null);
    try {
      await scheduleSalesRunFollowUp(agentId, scheduleTarget.id, {
        expected_revision: scheduleTarget.revision,
        due_at: iso,
        type: scheduleType,
        notes: scheduleNotes.trim() || null,
        ...(scheduleType === "EMAIL_FOLLOW_UP" ? { body_text: scheduleBody.trim() } : {}),
      });
      resetSchedule();
      setLoading(true);
      setRefreshKey((value) => value + 1);
    } catch (cause) {
      setScheduleError(actionError(cause, "The follow-up could not be scheduled."));
    } finally {
      setSchedulePending(false);
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
        <span className="inline-flex flex-wrap items-center gap-2">
          <SalesRunStatusBadge status={row.status} />
          {row.status === "RUNNING" ? <AiBadge label="Processing" /> : null}
          {row.status === "COMPLETED" ? (
            <span className="text-muted-foreground text-xs">
              Email sent
              {row.email_send?.completed_at
                ? ` ${formatTimestamp(row.email_send.completed_at)}`
                : ""}
            </span>
          ) : null}
          {row.follow_up ? (
            <FollowUpStatusBadge
              followUp={followUpAsLeadFollowUp(row.follow_up, row.lead_id)}
            />
          ) : null}
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
        description="Qualify an enquiry, review the draft, then send the approved response. Approval does not send the email. Sending is a separate action."
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
              {(row.status === "WAITING_APPROVAL" ||
                (row.status === "FAILED" && row.stage === "SEND")) &&
              row.response_draft_id ? (
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
              {canScheduleFollowUp(row) ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={schedulePending && scheduleTarget?.id === row.id}
                  onClick={() => openSchedule(row)}
                >
                  Schedule follow-up
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
      <Dialog
        open={scheduleTarget !== null && !scheduleConfirming}
        onOpenChange={(next) => {
          if (!next && !schedulePending) resetSchedule();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule follow-up</DialogTitle>
            <DialogDescription>
              Sending does not schedule a follow-up. Choose the type, due time, and
              email body. The follow-up worker sends due email follow-ups; manual
              follow-ups stay human-only.
            </DialogDescription>
          </DialogHeader>
          <form
            className="mt-4 grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (!scheduleReady) return;
              setScheduleError(null);
              setScheduleConfirming(true);
            }}
          >
            <FormField label="Type" htmlFor="sales-run-follow-up-type">
              <Select
                id="sales-run-follow-up-type"
                value={scheduleType}
                onChange={(event) =>
                  setScheduleType(event.target.value as LeadFollowUpType)
                }
              >
                <option value="EMAIL_FOLLOW_UP">Email follow-up</option>
                <option value="MANUAL_FOLLOW_UP">Manual follow-up</option>
              </Select>
            </FormField>
            <FormField
              label="Due date and time"
              htmlFor="sales-run-follow-up-due"
              required
            >
              <Input
                id="sales-run-follow-up-due"
                type="datetime-local"
                value={scheduleDueAt}
                onChange={(event) => setScheduleDueAt(event.target.value)}
                required
              />
            </FormField>
            {scheduleType === "EMAIL_FOLLOW_UP" ? (
              <FormField
                label="Email body"
                htmlFor="sales-run-follow-up-body"
                required
              >
                <Textarea
                  id="sales-run-follow-up-body"
                  value={scheduleBody}
                  onChange={(event) => setScheduleBody(event.target.value)}
                  maxLength={8000}
                  required
                />
              </FormField>
            ) : (
              <FormField label="Notes" htmlFor="sales-run-follow-up-notes">
                <Textarea
                  id="sales-run-follow-up-notes"
                  value={scheduleNotes}
                  onChange={(event) => setScheduleNotes(event.target.value)}
                  maxLength={4000}
                />
              </FormField>
            )}
            {scheduleType === "EMAIL_FOLLOW_UP" ? (
              <FormField label="Notes" htmlFor="sales-run-follow-up-email-notes">
                <Textarea
                  id="sales-run-follow-up-email-notes"
                  value={scheduleNotes}
                  onChange={(event) => setScheduleNotes(event.target.value)}
                  maxLength={4000}
                />
              </FormField>
            ) : null}
            {scheduleError && !scheduleConfirming ? (
              <p className="text-danger-text text-sm" role="alert">
                {scheduleError}
              </p>
            ) : null}
            <DialogFooter>
              <DialogCancel>Cancel</DialogCancel>
              <Button type="submit" disabled={!scheduleReady || schedulePending}>
                Review and schedule
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={scheduleTarget !== null && scheduleConfirming}
        onOpenChange={(next) => {
          if (!next && !schedulePending) {
            setScheduleConfirming(false);
          }
        }}
        title="Schedule this follow-up?"
        description="This creates a follow-up on the lead. It does not send email now. Due email follow-ups are sent later by the follow-up worker."
        confirmLabel={schedulePending ? "Scheduling…" : "Schedule follow-up"}
        confirmPending={schedulePending}
        onConfirm={() => void confirmSchedule()}
      >
        <dl className="mt-4 grid gap-2">
          <DetailRow label="Type" value={followUpTypeLabel(scheduleType)} />
          <DetailRow
            label="Due"
            value={
              schedulePayload()
                ? new Date(schedulePayload() as string).toLocaleString()
                : "—"
            }
          />
          {scheduleType === "EMAIL_FOLLOW_UP" ? (
            <DetailRow
              label="Message"
              value={
                <span className="whitespace-pre-wrap">{scheduleBody.trim() || "—"}</span>
              }
            />
          ) : null}
        </dl>
        {scheduleError ? (
          <p className="text-danger-text mt-3 text-sm" role="alert">
            {scheduleError}
          </p>
        ) : null}
      </ConfirmDialog>
    </section>
  );
}
