"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Check,
  Clipboard,
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
import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
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
  selectionUnavailable?: boolean;
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

function decisionPresentation(item: ApprovalQueueItem): {
  status: StatusValue;
  label: string;
  notice: string;
} {
  if (item.email?.status === "SENT") {
    return {
      status: "success",
      label: "Response sent",
      notice: "This response was sent to the customer.",
    };
  }
  if (
    item.email?.status === "FAILED" &&
    item.draft.review_status === "APPROVED"
  ) {
    return {
      status: "failed",
      label: "Send failed — retry available",
      notice:
        "The last send attempt failed. The approved response has not been sent.",
    };
  }
  if (item.draft.review_status === "APPROVED") {
    return {
      status: "success",
      label: "Approved — ready to send",
      notice: "Approved by human review. Sending remains a separate action.",
    };
  }
  if (item.draft.review_status === "REJECTED") {
    return {
      status: "failed",
      label: "Response rejected",
      notice: "This response will not be sent.",
    };
  }
  return {
    status: "warning",
    label: "Needs your review",
    notice: "This response has NOT been sent yet.",
  };
}

function CopyIdButton({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    },
    [],
  );

  async function copyId() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="xs"
      aria-label={copied ? `${label} copied` : `Copy ${label}`}
      onClick={() => void copyId()}
    >
      <Clipboard aria-hidden="true" />
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

function mergeDraftIntoItem(
  item: ApprovalQueueItem,
  draft: LeadResponseDraftResult,
): ApprovalQueueItem {
  const review = draft.review_status ?? item.draft.review_status;
  const pending = review === "GENERATED" || review === "EDITED";
  const approved = review === "APPROVED";
  const rejected = review === "REJECTED";
  const email = draft.latest_email_send
    ? {
        status: draft.latest_email_send.status,
        sent_at: draft.latest_email_send.completed_at,
      }
    : item.email;
  const sent = email?.status === "SENT" || email?.status === "PENDING";
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
    can_send:
      approved && Boolean(draft.response) && Boolean(item.lead.email) && !sent,
    updated_at: draft.updated_at ?? item.updated_at,
  };
}

export function ApprovalDetail({
  approval,
  loading = false,
  selectionUnavailable = false,
  onBack,
  onChanged,
}: ApprovalDetailProps) {
  const detailHeadingRef = useRef<HTMLHeadingElement>(null);
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
    if (approval) detailHeadingRef.current?.focus();
  }, [selectedDraftId, approval]);

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
          <Skeleton className="h-40 w-full" />
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
              tabIndex={-1}
              ref={detailHeadingRef}
            >
              {selectionUnavailable
                ? "Approval is not in this queue"
                : "What needs a decision?"}
            </h3>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              {selectionUnavailable
                ? "This draft is not on the current page or does not match the active status and search filters."
                : "Select an item from the queue to review the customer enquiry and AI-generated response."}
            </p>
          </div>
        </header>
        <div className="text-muted-foreground flex flex-1 items-center justify-center p-8 text-center text-sm leading-6">
          {selectionUnavailable
            ? "Open the matching status filter or clear the search to find it."
            : "No approval selected"}
        </div>
      </Card>
    );
  }

  const decision = decisionPresentation(approval);
  const analysis = qualification?.analysis ?? null;
  const company = approval.lead.company?.trim();
  const email = approval.lead.email?.trim();
  const showApprove = approval.can_approve;
  const showReject = approval.can_reject;
  const showEdit = approval.can_edit;
  const showSend = approval.can_send;
  const linkedWaitingRun =
    approval.sales_run?.status === "WAITING_APPROVAL";

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
      setActionSuccess("Approved — ready to send. Approval does not send email.");
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
          ? "Response rejected. Linked SalesRun was cancelled."
          : "Response rejected.",
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
      setActionSuccess(
        "Draft updated. It still needs your review before sending.",
      );
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
      setActionSuccess("Response sent.");
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
            <p className="text-muted-foreground text-[0.65rem] font-medium tracking-wide uppercase">
              {decision.label}
            </p>
            <h3
              id="approval-detail-title"
              ref={detailHeadingRef}
              tabIndex={-1}
              className="mt-1 text-base font-semibold tracking-tight"
            >
              {approval.lead.name}
            </h3>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              {[company, email].filter(Boolean).join(" · ") ||
                "No company or email on file"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={decision.status} label={decision.label} />
          <Link
            href={`/leads/${encodeURIComponent(approval.lead_id)}`}
            className={cn(
              buttonVariants({ variant: "ghost", size: "sm" }),
              "text-muted-foreground",
            )}
          >
            Open Customer 360
            <ExternalLink aria-hidden="true" />
          </Link>
        </div>
      </header>

      <div className="flex flex-1 flex-col gap-7 overflow-y-auto p-5 sm:p-6">
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

        <p
          className="border-border bg-surface-subtle text-muted-foreground rounded-md border px-3 py-2 text-sm leading-6"
          role="status"
        >
          {decision.notice}
        </p>

        <section aria-labelledby="approval-enquiry-title" className="grid gap-2">
          <h4
            id="approval-enquiry-title"
            className="text-muted-foreground text-xs font-medium tracking-wide uppercase"
          >
            Customer enquiry
          </h4>
          <p className="border-border bg-muted/50 text-foreground max-w-3xl whitespace-pre-wrap rounded-md border p-4 text-sm leading-7">
            {approval.enquiry}
          </p>
        </section>

        <section aria-labelledby="approval-response-title" className="grid gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <h4
              id="approval-response-title"
              className="text-sm font-semibold tracking-tight"
            >
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
                  rows={10}
                  required
                  className="min-h-48 leading-7"
                />
              </FormField>
              <p className="text-muted-foreground text-xs tabular-nums">
                {editText.length.toLocaleString()} / 8,000 characters
              </p>
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
            <div className="border-ai-border bg-ai/5 max-w-3xl rounded-md border p-4 sm:p-5">
              <p className="text-foreground whitespace-pre-wrap text-[0.95rem] leading-7">
                {approval.draft.response?.trim() || "No response text."}
              </p>
            </div>
          )}
        </section>

        <section
          aria-labelledby="approval-context-title"
          className="border-border grid gap-5 border-t pt-6"
        >
          <h4
            id="approval-context-title"
            className="text-muted-foreground text-xs font-medium tracking-wide uppercase"
          >
            AI / Sales context
          </h4>

          <div className="grid gap-5 lg:grid-cols-2">
            <div className="grid gap-2">
              <h5 className="text-sm font-medium">Qualification</h5>
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
                  {analysis.missing_information.length > 0 ? (
                    <DetailRow
                      label="Missing information"
                      value={analysis.missing_information.join(", ")}
                    />
                  ) : null}
                </dl>
              ) : (
                <p className="text-muted-foreground text-sm leading-6">
                  No qualification analysis is available for this lead yet.
                </p>
              )}
            </div>

            <div className="grid gap-4">
              <div className="grid gap-2">
                <h5 className="text-sm font-medium">Sales Agent</h5>
                {approval.sales_run ? (
                  <dl className="grid gap-3">
                    <DetailRow
                      label="Sales Agent"
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
                  <p className="text-muted-foreground text-sm leading-6">
                    Standalone draft — not linked to a SalesRun.
                  </p>
                )}
              </div>

              <div className="grid gap-2">
                <h5 className="text-sm font-medium">Email status</h5>
                <p className="text-sm leading-6">{decision.label}</p>
                {approval.draft.review_status === "APPROVED" &&
                !approval.lead.email &&
                approval.email?.status !== "SENT" ? (
                  <p className="text-muted-foreground text-xs leading-5">
                    Add an email address to this customer before sending.
                  </p>
                ) : null}
                <p className="text-muted-foreground text-xs">
                  Updated <RelativeTime value={approval.updated_at} />
                  {leadDetail?.phone ? ` · Phone ${leadDetail.phone}` : null}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section
          aria-labelledby="approval-metadata-title"
          className="border-border grid gap-3 border-t pt-6"
        >
          <h4
            id="approval-metadata-title"
            className="text-muted-foreground text-xs font-medium tracking-wide uppercase"
          >
            Metadata
          </h4>
          <dl className="grid gap-3">
            <DetailRow
              label="Draft ID"
              value={
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs break-all">
                    {approval.draft_id}
                  </span>
                  <CopyIdButton label="draft ID" value={approval.draft_id} />
                </span>
              }
            />
            <DetailRow
              label="Lead ID"
              value={
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs break-all">
                    {approval.lead_id}
                  </span>
                  <CopyIdButton label="lead ID" value={approval.lead_id} />
                </span>
              }
            />
            {approval.sales_run ? (
              <DetailRow
                label="SalesRun ID"
                value={
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs break-all">
                      {approval.sales_run.id}
                    </span>
                    <CopyIdButton
                      label="SalesRun ID"
                      value={approval.sales_run.id}
                    />
                  </span>
                }
              />
            ) : null}
            <DetailRow label="Revision" value={approval.draft.revision} />
            <DetailRow
              label="Created"
              value={<RelativeTime value={approval.draft.created_at} />}
            />
            <DetailRow
              label="Updated"
              value={<RelativeTime value={approval.draft.updated_at} />}
            />
          </dl>
        </section>
      </div>

      <footer
        className="border-border bg-surface-subtle flex flex-col gap-3 border-t p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between"
        aria-label="Decision"
      >
        <p className="text-muted-foreground text-xs leading-5 sm:max-w-sm">
          {showSend
            ? "Send is a human-controlled outbound action."
            : showApprove
              ? "Approve marks the response ready to send. It does not send email."
              : decision.notice}
        </p>
        <div className="flex flex-wrap justify-end gap-2">
          {showEdit ? (
            <Button
              type="button"
              variant="outline"
              disabled={pending || editing}
              onClick={() => {
                setEditing(true);
                setEditText(approval.draft.response ?? "");
                setActionSuccess(null);
              }}
            >
              <Pencil aria-hidden="true" />
              Edit
            </Button>
          ) : null}
          {showReject ? (
            <Button
              type="button"
              variant="outline"
              disabled={pending}
              onClick={() => setConfirmReject(true)}
            >
              <X aria-hidden="true" />
              Reject
            </Button>
          ) : null}
          {showApprove ? (
            <Button
              type="button"
              disabled={pending}
              onClick={() => setConfirmApprove(true)}
            >
              <Check aria-hidden="true" />
              Approve
            </Button>
          ) : null}
          {showSend ? (
            <Button
              type="button"
              variant="secondary"
              disabled={pending}
              onClick={() => setConfirmSend(true)}
            >
              <Send aria-hidden="true" />
              Send response
            </Button>
          ) : null}
        </div>
      </footer>

      <ConfirmDialog
        open={confirmApprove}
        onOpenChange={setConfirmApprove}
        title="Approve this response?"
        description="Approving this response will mark it ready to send. It will NOT send the email automatically."
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
        description={
          linkedWaitingRun
            ? "The AI response will be rejected. The linked SalesRun waiting for approval will be cancelled. No email will be sent."
            : "The AI response will be rejected. No email will be sent."
        }
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
            placeholder="Optional note for your team"
          />
        </FormField>
      </ConfirmDialog>
      <ConfirmDialog
        open={confirmSend}
        onOpenChange={setConfirmSend}
        title="Send approved response?"
        description="This will send the approved response to the customer. This is a human-controlled outbound action."
        confirmLabel={pending ? "Sending…" : "Send"}
        confirmPending={pending}
        onConfirm={() => {
          void handleSend();
        }}
      />
    </Card>
  );
}
