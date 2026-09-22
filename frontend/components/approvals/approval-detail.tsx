"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";
import {
  ArrowLeft,
  Check,
  ExternalLink,
  Pencil,
  Send,
  X,
} from "lucide-react";

import { AiBadge } from "@/components/ai/ai-badge";
import { DetailRow } from "@/components/data-display/detail-row";
import { FormField } from "@/components/forms/form-field";
import { Textarea } from "@/components/forms/textarea";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { RelativeTime } from "@/components/ui/relative-time";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/api/client";
import {
  approveLeadResponseDraft,
  getLead,
  getLeadQualification,
  rejectLeadResponseDraft,
  sendLeadResponseDraft,
  updateLeadResponseDraft,
} from "@/lib/api/leads";
import { getSalesRun, sendSalesRun } from "@/lib/api/sales-runs";
import { draftReviewLabels, inboxSourceLabels } from "@/lib/inbox-labels";
import { statusPresentation } from "@/lib/status";
import { cn } from "@/lib/utils";
import type {
  ApprovalQueueItem,
  Lead,
  LeadQualificationResult,
  LeadResponseDraftResult,
} from "@/types/api";

type ApprovalDetailProps = {
  approval?: ApprovalQueueItem | null;
  loading?: boolean;
  onBack?: () => void;
  onChanged?: (item: ApprovalQueueItem) => void;
};

const stageLabels: Record<string, string> = {
  MATCH_LEAD: "Match lead",
  QUALIFY: "Qualify",
  DRAFT: "Draft",
  AWAIT_APPROVAL: "Await approval",
  SEND: "Send",
  DONE: "Done",
};

const intentLabels: Record<string, string> = {
  REQUEST_DEMO: "Request demo",
  REQUEST_PRICING: "Request pricing",
  GENERAL_ENQUIRY: "General enquiry",
  SUPPORT_REQUEST: "Support request",
  OTHER: "Other",
};

function actionError(cause: unknown, fallback: string) {
  if (!(cause instanceof ApiError)) return fallback;
  if (cause.status === 401) return "Your session expired. Sign in again.";
  if (cause.status === 403) return "You do not have permission for this action.";
  if (cause.status === 404) return "This approval could not be found.";
  if (cause.status === 409) {
    return "This draft changed. Refresh and review the latest version.";
  }
  if (cause.status === 422) return "This lead has no email address.";
  if (cause.status === 502) return "The email provider could not send this message.";
  if (cause.status === 503) return "Email provider is not configured.";
  if (
    typeof cause.body === "object" &&
    cause.body &&
    "detail" in cause.body &&
    typeof cause.body.detail === "string"
  ) {
    return cause.body.detail;
  }
  return fallback;
}

function emailStateLabel(item: ApprovalQueueItem) {
  if (item.email?.status === "SENT") return "Sent";
  if (item.email?.status === "FAILED") return "Failed";
  if (item.email?.status === "PENDING") return "Sending…";
  if (item.draft.review_status === "APPROVED") return "Ready to send";
  if (item.draft.review_status === "REJECTED") return "Not sent";
  return "Not sent";
}

function mergeDraftIntoItem(
  item: ApprovalQueueItem,
  draft: LeadResponseDraftResult,
): ApprovalQueueItem {
  const review = draft.review_status ?? item.draft.review_status;
  const pending =
    review === "GENERATED" || review === "EDITED";
  const approved = review === "APPROVED";
  const rejected = review === "REJECTED";
  const email = draft.latest_email_send
    ? {
        status: draft.latest_email_send.status,
        sent_at: draft.latest_email_send.completed_at,
      }
    : item.email;
  const sent =
    email?.status === "SENT" || email?.status === "PENDING";
  return {
    ...item,
    enquiry: draft.enquiry,
    draft: {
      response: draft.response,
      review_status: review,
      revision: draft.revision,
      created_at: draft.created_at,
      updated_at: draft.updated_at ?? item.draft.updated_at,
    },
    email,
    needs_approval: pending,
    can_approve: pending && Boolean(draft.response),
    can_reject: pending || approved,
    can_edit: !rejected && draft.status === "COMPLETED",
    can_send: approved && Boolean(draft.response) && Boolean(item.lead.email) && !sent,
    updated_at: draft.updated_at ?? item.updated_at,
  };
}

export function ApprovalDetail({
  approval,
  loading = false,
  onBack,
  onChanged,
}: ApprovalDetailProps) {
  const [leadDetail, setLeadDetail] = useState<Lead | null>(null);
  const [qualification, setQualification] =
    useState<LeadQualificationResult | null>(null);
  const [contextLoading, setContextLoading] = useState(Boolean(approval));
  const [actionErrorMessage, setActionErrorMessage] = useState<string | null>(
    null,
  );
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(approval?.draft.response ?? "");
  const [confirmApprove, setConfirmApprove] = useState(false);
  const [confirmReject, setConfirmReject] = useState(false);
  const [confirmSend, setConfirmSend] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  const selectedLeadId = approval?.lead_id;
  const selectedDraftId = approval?.draft_id;

  useEffect(() => {
    if (!selectedLeadId) {
      return;
    }
    let cancelled = false;
    void getLead(selectedLeadId)
      .then(async (lead) => {
        if (cancelled) return;
        setLeadDetail(lead);
        const qualificationId = lead.latest_qualification?.id;
        if (
          !qualificationId ||
          lead.latest_qualification?.status !== "COMPLETED"
        ) {
          setQualification(null);
          return;
        }
        try {
          const detail = await getLeadQualification(lead.id, qualificationId);
          if (!cancelled) setQualification(detail);
        } catch {
          if (!cancelled) setQualification(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLeadDetail(null);
          setQualification(null);
        }
      })
      .finally(() => {
        if (!cancelled) setContextLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedDraftId, selectedLeadId]);

  if (loading) {
    return (
      <Card
        as="section"
        className="flex min-h-[38rem] min-w-0 flex-col overflow-hidden p-5"
        aria-labelledby="approval-detail-title"
      >
        <h3 id="approval-detail-title" className="sr-only">
          Approval detail
        </h3>
        <div className="grid gap-3" role="status">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-64" />
          <Skeleton className="mt-4 h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <span className="sr-only">Loading approval detail</span>
        </div>
      </Card>
    );
  }

  if (!approval) {
    return (
      <Card
        as="section"
        className="flex min-h-[38rem] min-w-0 flex-col overflow-hidden"
        aria-labelledby="approval-detail-title"
      >
        <header className="border-border flex items-start gap-2 border-b px-4 py-4 sm:px-5">
          {onBack ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="Back to approval queue"
              onClick={onBack}
            >
              <ArrowLeft aria-hidden="true" />
            </Button>
          ) : null}
          <div>
            <h3
              id="approval-detail-title"
              className="text-base font-medium tracking-tight"
            >
              Approval detail
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Select an item from the queue to review the customer enquiry and
              AI response.
            </p>
          </div>
        </header>
        <div className="text-muted-foreground flex flex-1 items-center justify-center p-8 text-center text-sm">
          No approval selected
        </div>
      </Card>
    );
  }

  const review = approval.draft.review_status;
  const reviewBadge = review
    ? statusPresentation(review, draftReviewLabels[review] ?? review)
    : statusPresentation("PENDING", "Needs review");
  const analysis = qualification?.analysis ?? null;

  async function handleApprove() {
    if (!approval || pending) return;
    setConfirmApprove(false);
    setPending(true);
    setActionErrorMessage(null);
    try {
      const saved = await approveLeadResponseDraft(
        approval.lead_id,
        approval.draft_id,
        { expected_revision: approval.draft.revision },
      );
      const next = mergeDraftIntoItem(approval, saved);
      onChanged?.(next);
      setActionSuccess("Approved. Ready to send — approval does not send email.");
    } catch (cause) {
      setActionErrorMessage(actionError(cause, "Could not approve this draft."));
    } finally {
      setPending(false);
    }
  }

  async function handleReject() {
    if (!approval || pending) return;
    setConfirmReject(false);
    setPending(true);
    setActionErrorMessage(null);
    try {
      const saved = await rejectLeadResponseDraft(
        approval.lead_id,
        approval.draft_id,
        {
          expected_revision: approval.draft.revision,
          reason: rejectReason.trim() || null,
        },
      );
      const next = mergeDraftIntoItem(approval, saved);
      if (next.sales_run?.status === "WAITING_APPROVAL") {
        next.sales_run = {
          ...next.sales_run,
          status: "CANCELLED",
        };
      }
      onChanged?.(next);
      setActionSuccess(
        next.sales_run
          ? "Rejected. Linked Sales Run was cancelled."
          : "Draft rejected.",
      );
      setRejectReason("");
    } catch (cause) {
      setActionErrorMessage(actionError(cause, "Could not reject this draft."));
    } finally {
      setPending(false);
    }
  }

  async function handleSaveEdit(event: FormEvent) {
    event.preventDefault();
    if (!approval || pending) return;
    setPending(true);
    setActionErrorMessage(null);
    try {
      const saved = await updateLeadResponseDraft(
        approval.lead_id,
        approval.draft_id,
        {
          response: editText.trim(),
          expected_revision: approval.draft.revision,
        },
      );
      const next = mergeDraftIntoItem(approval, saved);
      onChanged?.(next);
      setEditing(false);
      setActionSuccess("Draft updated. It still needs approval before sending.");
    } catch (cause) {
      setActionErrorMessage(actionError(cause, "Could not save this edit."));
    } finally {
      setPending(false);
    }
  }

  async function handleSend() {
    if (!approval || pending) return;
    setConfirmSend(false);
    setPending(true);
    setActionErrorMessage(null);
    try {
      if (approval.sales_run) {
        const run = await getSalesRun(
          approval.sales_run.agent_id,
          approval.sales_run.id,
        );
        const sent = await sendSalesRun(run.agent_id, run.id, {
          expected_revision: run.revision,
        });
        const next: ApprovalQueueItem = {
          ...approval,
          sales_run: {
            id: sent.id,
            status: sent.status,
            stage: sent.stage,
            agent_id: sent.agent_id,
            agent_name: approval.sales_run.agent_name,
          },
          email: sent.email_send
            ? {
                status: sent.email_send.status,
                sent_at: sent.email_send.completed_at,
              }
            : approval.email,
          can_send: false,
          can_approve: false,
          needs_approval: false,
        };
        onChanged?.(next);
      } else {
        const sent = await sendLeadResponseDraft(
          approval.lead_id,
          approval.draft_id,
        );
        const next: ApprovalQueueItem = {
          ...approval,
          email: {
            status: sent.status,
            sent_at: sent.completed_at,
          },
          can_send: sent.status !== "SENT" && sent.status !== "PENDING",
          needs_approval: false,
          can_approve: false,
        };
        onChanged?.(next);
      }
      setActionSuccess("Email sent.");
    } catch (cause) {
      setActionErrorMessage(actionError(cause, "Could not send this email."));
    } finally {
      setPending(false);
    }
  }

  return (
    <Card
      as="section"
      className="flex min-h-[38rem] min-w-0 flex-col overflow-hidden"
      aria-labelledby="approval-detail-title"
    >
      <header className="border-border flex flex-wrap items-start justify-between gap-3 border-b px-4 py-4 sm:px-5">
        <div className="flex min-w-0 items-start gap-2">
          {onBack ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="Back to approval queue"
              onClick={onBack}
            >
              <ArrowLeft aria-hidden="true" />
            </Button>
          ) : null}
          <div className="min-w-0">
            <h3
              id="approval-detail-title"
              className="text-base font-medium tracking-tight"
            >
              {approval.lead.name}
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Decide whether this AI response is ready for the customer.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={reviewBadge.status} label={reviewBadge.label} />
          <Link
            href={`/leads/${encodeURIComponent(approval.lead_id)}`}
            className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
          >
            Open Customer 360
            <ExternalLink aria-hidden="true" />
          </Link>
        </div>
      </header>

      <div className="flex flex-1 flex-col gap-6 overflow-y-auto p-5 sm:p-6">
        {actionSuccess ? (
          <p
            className="border-success/25 bg-success/5 text-success-text rounded-md border px-3 py-2 text-sm"
            role="status"
          >
            {actionSuccess}
          </p>
        ) : null}
        {actionErrorMessage ? (
          <p
            className="border-destructive/25 bg-destructive/5 text-danger-text rounded-md border px-3 py-2 text-sm"
            role="alert"
          >
            {actionErrorMessage}
          </p>
        ) : null}

        <section aria-labelledby="approval-customer-title" className="grid gap-3">
          <h4 id="approval-customer-title" className="text-sm font-medium">
            Customer
          </h4>
          <dl className="grid gap-3 sm:grid-cols-2">
            <DetailRow label="Name" value={approval.lead.name} />
            <DetailRow
              label="Email"
              value={
                approval.lead.email ? (
                  <a
                    className="text-primary underline-offset-2 hover:underline"
                    href={`mailto:${approval.lead.email}`}
                  >
                    {approval.lead.email}
                  </a>
                ) : (
                  "—"
                )
              }
            />
            <DetailRow label="Company" value={approval.lead.company ?? "—"} />
            <DetailRow
              label="Lead status"
              value={approval.lead.status.replaceAll("_", " ")}
            />
            <DetailRow
              label="Source"
              value={inboxSourceLabels[approval.lead.source]}
            />
            <DetailRow
              label="Updated"
              value={<RelativeTime value={approval.updated_at} />}
            />
          </dl>
        </section>

        <section aria-labelledby="approval-enquiry-title" className="grid gap-2">
          <h4 id="approval-enquiry-title" className="text-sm font-medium">
            Customer enquiry
          </h4>
          <p className="border-border bg-muted/40 whitespace-pre-wrap rounded-md border p-3 text-sm leading-6">
            {approval.enquiry}
          </p>
        </section>

        <section aria-labelledby="approval-response-title" className="grid gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <h4 id="approval-response-title" className="text-sm font-medium">
              AI-generated response
            </h4>
            <AiBadge label="Generated" />
          </div>
          {editing ? (
            <form className="grid gap-3" onSubmit={handleSaveEdit}>
              <FormField label="Edit response" htmlFor="approval-edit-response">
                <Textarea
                  id="approval-edit-response"
                  value={editText}
                  onChange={(event) => setEditText(event.target.value)}
                  rows={8}
                  required
                />
              </FormField>
              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={pending || !editText.trim()}>
                  Save edit
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={pending}
                  onClick={() => {
                    setEditing(false);
                    setEditText(approval.draft.response ?? "");
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          ) : (
            <p className="border-ai-border bg-ai/5 whitespace-pre-wrap rounded-md border p-3 text-sm leading-6">
              {approval.draft.response?.trim() || "No response text."}
            </p>
          )}
        </section>

        <section
          aria-labelledby="approval-qualification-title"
          className="grid gap-2"
        >
          <h4 id="approval-qualification-title" className="text-sm font-medium">
            Qualification
          </h4>
          {contextLoading ? (
            <div role="status" className="grid gap-2">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-16 w-full" />
              <span className="sr-only">Loading qualification</span>
            </div>
          ) : analysis ? (
            <dl className="grid gap-3">
              <DetailRow label="Summary" value={analysis.summary} />
              <DetailRow
                label="Intent"
                value={intentLabels[analysis.intent] ?? analysis.intent}
              />
              <DetailRow
                label="Confidence"
                value={`${Math.round(analysis.confidence * 100)}%`}
              />
              <DetailRow
                label="Buying signals"
                value={
                  analysis.buying_signals.length > 0
                    ? analysis.buying_signals.join(", ")
                    : "None listed"
                }
              />
              <DetailRow
                label="Missing information"
                value={
                  analysis.missing_information.length > 0
                    ? analysis.missing_information.join(", ")
                    : "None listed"
                }
              />
            </dl>
          ) : (
            <p className="text-muted-foreground text-sm">
              No qualification analysis is available for this lead yet.
            </p>
          )}
        </section>

        <section aria-labelledby="approval-agent-title" className="grid gap-2">
          <h4 id="approval-agent-title" className="text-sm font-medium">
            Sales Agent
          </h4>
          {approval.sales_run ? (
            <dl className="grid gap-3 sm:grid-cols-2">
              <DetailRow
                label="Agent"
                value={approval.sales_run.agent_name ?? "Sales Agent"}
              />
              <DetailRow
                label="SalesRun status"
                value={approval.sales_run.status.replaceAll("_", " ")}
              />
              <DetailRow
                label="Stage"
                value={
                  stageLabels[approval.sales_run.stage] ??
                  approval.sales_run.stage
                }
              />
            </dl>
          ) : (
            <p className="text-muted-foreground text-sm">Standalone draft</p>
          )}
        </section>

        <section aria-labelledby="approval-email-title" className="grid gap-2">
          <h4 id="approval-email-title" className="text-sm font-medium">
            Email status
          </h4>
          <p className="text-sm">
            {emailStateLabel(approval)}
            {approval.draft.review_status === "APPROVED" &&
            approval.email?.status !== "SENT" ? (
              <span className="text-muted-foreground">
                {" "}
                — Approved is not the same as Sent.
              </span>
            ) : null}
          </p>
          {leadDetail?.phone ? (
            <p className="text-muted-foreground text-xs">
              Phone:{" "}
              <a className="underline-offset-2 hover:underline" href={`tel:${leadDetail.phone}`}>
                {leadDetail.phone}
              </a>
            </p>
          ) : null}
        </section>
      </div>

      <footer className="border-border bg-surface-subtle flex flex-wrap justify-end gap-2 border-t p-4">
        <Button
          type="button"
          variant="outline"
          disabled={!approval.can_edit || pending || editing}
          onClick={() => {
            setEditing(true);
            setEditText(approval.draft.response ?? "");
            setActionSuccess(null);
          }}
        >
          <Pencil aria-hidden="true" />
          Edit
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!approval.can_reject || pending}
          onClick={() => setConfirmReject(true)}
        >
          <X aria-hidden="true" />
          Reject
        </Button>
        <Button
          type="button"
          disabled={!approval.can_approve || pending}
          onClick={() => setConfirmApprove(true)}
        >
          <Check aria-hidden="true" />
          Approve
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={!approval.can_send || pending}
          onClick={() => setConfirmSend(true)}
        >
          <Send aria-hidden="true" />
          Send
        </Button>
      </footer>

      <ConfirmDialog
        open={confirmApprove}
        onOpenChange={setConfirmApprove}
        title="Approve this response?"
        description="Approval does not send the email. Sending remains a separate action."
        confirmLabel={pending ? "Approving…" : "Approve"}
        confirmPending={pending}
        onConfirm={() => {
          void handleApprove();
        }}
      />
      <ConfirmDialog
        open={confirmReject}
        onOpenChange={setConfirmReject}
        title="Reject this response?"
        description="If this draft belongs to a waiting Sales Run, that run will be cancelled."
        confirmLabel={pending ? "Rejecting…" : "Reject"}
        variant="destructive"
        confirmPending={pending}
        onConfirm={() => {
          void handleReject();
        }}
      >
        <FormField label="Reason (optional)" htmlFor="approval-reject-reason">
          <Textarea
            id="approval-reject-reason"
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
            rows={3}
          />
        </FormField>
      </ConfirmDialog>
      <ConfirmDialog
        open={confirmSend}
        onOpenChange={setConfirmSend}
        title="Send approved response?"
        description="This sends the approved response to the customer. This is an external action."
        confirmLabel={pending ? "Sending…" : "Send"}
        confirmPending={pending}
        onConfirm={() => {
          void handleSend();
        }}
      />
    </Card>
  );
}
