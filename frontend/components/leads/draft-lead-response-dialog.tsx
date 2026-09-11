"use client";

import { type FormEvent, useEffect, useState } from "react";

import { AiBadge } from "@/components/ai/ai-badge";
import { DetailRow } from "@/components/data-display/detail-row";
import { FormField } from "@/components/forms/form-field";
import { Textarea } from "@/components/forms/textarea";
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
import { StatusBadge } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";
import { ApiError } from "@/lib/api/client";
import {
  approveLeadResponseDraft,
  generateLeadResponseDraft,
  getLeadResponseDraft,
  rejectLeadResponseDraft,
  sendLeadResponseDraft,
  updateLeadResponseDraft,
} from "@/lib/api/leads";
import type {
  Lead,
  LeadEmailSendResult,
  LeadResponseDraftResult,
  LeadResponseReviewStatus,
} from "@/types/api";

type DraftLeadResponseDialogProps = {
  open: boolean;
  lead: Lead | null;
  draftId?: string | null;
  onOpenChange: (open: boolean) => void;
  onCompleted: (result: LeadResponseDraftResult) => void;
};

const reviewLabels: Record<LeadResponseReviewStatus, string> = {
  GENERATED: "Awaiting review",
  EDITED: "Edited — needs review",
  APPROVED: "Approved (not sent)",
  REJECTED: "Rejected",
};

const EMAIL_SUBJECT = "Re: Your enquiry";

function isEmailSendResult(value: unknown): value is LeadEmailSendResult {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    "recipient_email" in value &&
    "id" in value
  );
}

function errorMessage(cause: unknown, kind: "review" | "send" = "review") {
  if (!(cause instanceof ApiError)) {
    return "The request could not be completed. Please try again.";
  }
  if (cause.status === 401) {
    return "Your session expired. Sign in again.";
  }
  if (cause.status === 403) {
    return kind === "send"
      ? "You do not have permission to send this email."
      : "You do not have permission to review this draft.";
  }
  if (cause.status === 404) {
    return "This draft could not be found.";
  }
  if (cause.status === 409) {
    if (kind === "send") {
      if (isEmailSendResult(cause.body) && cause.body.status === "SENT") {
        return "This email was already sent.";
      }
      if (
        typeof cause.body === "object" &&
        cause.body &&
        "detail" in cause.body &&
        typeof cause.body.detail === "string" &&
        cause.body.detail.toLowerCase().includes("already sent")
      ) {
        return "This email was already sent.";
      }
      return "This draft is not approved for sending.";
    }
    return "This draft changed. Refresh and review the latest version.";
  }
  if (cause.status === 422 && kind === "send") {
    return "This lead has no email address.";
  }
  if (cause.status === 503) {
    if (kind === "send") {
      return "Email provider is not configured.";
    }
    return "AI provider is not configured.";
  }
  if (cause.status === 502 && kind === "send") {
    return "The email provider could not send this message.";
  }
  if (cause.status === 422) {
    return "Review the text and correct invalid fields.";
  }
  if (typeof cause.body === "object" && cause.body && "detail" in cause.body) {
    const detail = cause.body.detail;
    if (typeof detail === "string") return detail;
  }
  return "The request could not be completed. Please try again.";
}

export function DraftLeadResponseDialog({
  open,
  lead,
  draftId = null,
  onOpenChange,
  onCompleted,
}: DraftLeadResponseDialogProps) {
  const [enquiry, setEnquiry] = useState(lead?.notes ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<LeadResponseDraftResult | null>(null);
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [confirmingApprove, setConfirmingApprove] = useState(false);
  const [confirmingSend, setConfirmingSend] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!open || !lead || !draftId) return;
    let cancelled = false;
    void getLeadResponseDraft(lead.id, draftId)
      .then((draft) => {
        if (!cancelled) {
          setResult(draft);
          setEnquiry(draft.enquiry);
        }
      })
      .catch((cause) => {
        if (!cancelled) setError(errorMessage(cause));
      })
      .finally(() => {
        if (!cancelled) setPending(false);
      });
    return () => {
      cancelled = true;
    };
  }, [draftId, lead, open]);

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lead || pending) return;
    setError(null);
    setCopied(false);
    setPending(true);
    try {
      const saved = await generateLeadResponseDraft(lead.id, {
        enquiry: enquiry.trim(),
      });
      setResult(saved);
      setEditing(false);
      onCompleted(saved);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  async function saveEdit() {
    if (!lead || !result || pending) return;
    setError(null);
    setPending(true);
    try {
      const saved = await updateLeadResponseDraft(lead.id, result.id, {
        response: editText.trim(),
        expected_revision: result.revision,
      });
      setResult(saved);
      setEditing(false);
      onCompleted(saved);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  async function approve() {
    if (!lead || !result || pending) return;
    setConfirmingApprove(false);
    setError(null);
    setPending(true);
    try {
      const saved = await approveLeadResponseDraft(lead.id, result.id, {
        expected_revision: result.revision,
      });
      setResult(saved);
      onCompleted(saved);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  async function reject() {
    if (!lead || !result || pending) return;
    setError(null);
    setPending(true);
    try {
      const saved = await rejectLeadResponseDraft(lead.id, result.id, {
        expected_revision: result.revision,
        reason: rejectReason.trim() || null,
      });
      setResult(saved);
      setRejecting(false);
      setRejectReason("");
      onCompleted(saved);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  async function sendEmail() {
    if (!lead || !result || sending || pending) return;
    setConfirmingSend(false);
    setError(null);
    setSending(true);
    try {
      const saved = await sendLeadResponseDraft(lead.id, result.id);
      setResult({ ...result, latest_email_send: saved });
      onCompleted({ ...result, latest_email_send: saved });
    } catch (cause) {
      if (cause instanceof ApiError && isEmailSendResult(cause.body)) {
        setResult({ ...result, latest_email_send: cause.body });
      }
      setError(errorMessage(cause, "send"));
    } finally {
      setSending(false);
    }
  }

  async function copyDraft() {
    if (!result?.response) return;
    await navigator.clipboard.writeText(result.response);
    setCopied(true);
  }

  const reviewable =
    result?.status === "COMPLETED" &&
    result.review_status !== "REJECTED" &&
    Boolean(result.response);
  const canDecide =
    result?.review_status === "GENERATED" || result?.review_status === "EDITED";
  const alreadySent = result?.latest_email_send?.status === "SENT";
  const canSend =
    result?.review_status === "APPROVED" &&
    Boolean(lead?.email) &&
    !alreadySent &&
    !editing;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setResult(null);
          setError(null);
          setPending(false);
          setCopied(false);
          setEditing(false);
          setRejecting(false);
          setRejectReason("");
          setConfirmingApprove(false);
          setConfirmingSend(false);
          setSending(false);
          setEnquiry(lead?.notes ?? "");
        }
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Draft response</DialogTitle>
          <DialogDescription>
            AI generated this. Human review is required. Nothing has been sent.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4">
          <AiBadge label="Generated" />
        </div>
        {lead ? (
          <p className="text-muted-foreground mt-4 text-sm">
            CRM status for {lead.name}: {lead.status}
          </p>
        ) : null}
        <form className="mt-4 grid gap-4" onSubmit={handleGenerate}>
          <FormField label="Customer enquiry" htmlFor="lead-response-enquiry" required>
            <Textarea
              id="lead-response-enquiry"
              value={enquiry}
              onChange={(event) => setEnquiry(event.target.value)}
              maxLength={8000}
              required
            />
          </FormField>
          {pending ? (
            <div className="flex flex-wrap items-center gap-2" role="status">
              <AiBadge label="Processing" />
              <p className="text-muted-foreground text-sm">Working…</p>
            </div>
          ) : null}
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          {result?.response ? (
            <div className="grid gap-2">
              <div className="flex flex-wrap items-center gap-2">
                {result.review_status ? (
                  <StatusBadge
                    {...statusPresentation(
                      result.review_status,
                      reviewLabels[result.review_status],
                    )}
                  />
                ) : null}
              </div>
              {alreadySent ? (
                <p className="text-sm" role="status">
                  SENT
                </p>
              ) : null}
              {result.human_edited && result.original_response ? (
                <p className="text-muted-foreground text-xs leading-5 whitespace-pre-wrap">
                  Original AI text: {result.original_response}
                </p>
              ) : null}
              {editing ? (
                <FormField label="Edited response" htmlFor="lead-response-edit" required>
                  <Textarea
                    id="lead-response-edit"
                    value={editText}
                    onChange={(event) => setEditText(event.target.value)}
                    maxLength={8000}
                    required
                  />
                </FormField>
              ) : (
                <p className="border-border bg-muted/40 rounded-md border p-3 text-sm leading-6 whitespace-pre-wrap">
                  {result.response}
                </p>
              )}
              {result.review_status === "REJECTED" && result.rejection_reason ? (
                <p className="text-sm">Rejection reason: {result.rejection_reason}</p>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => void copyDraft()}>
                  {copied ? "Copied" : "Copy draft"}
                </Button>
                {reviewable && !editing ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={pending}
                    onClick={() => {
                      setEditText(result.response ?? "");
                      setEditing(true);
                    }}
                  >
                    Edit
                  </Button>
                ) : null}
                {editing ? (
                  <>
                    <Button
                      type="button"
                      size="sm"
                      disabled={pending || !editText.trim()}
                      onClick={() => void saveEdit()}
                    >
                      {pending ? "Saving…" : "Save changes"}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={pending}
                      onClick={() => setEditing(false)}
                    >
                      Cancel
                    </Button>
                  </>
                ) : null}
                {canDecide && !editing ? (
                  <>
                    <Button
                      type="button"
                      size="sm"
                      disabled={pending}
                      onClick={() => setConfirmingApprove(true)}
                    >
                      Approve
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={pending}
                      onClick={() => setRejecting(true)}
                    >
                      Reject
                    </Button>
                  </>
                ) : null}
                {canSend ? (
                  <Button
                    type="button"
                    size="sm"
                    disabled={pending || sending}
                    onClick={() => setConfirmingSend(true)}
                  >
                    {sending ? "Sending…" : "Send email"}
                  </Button>
                ) : null}
              </div>
              {rejecting ? (
                <div className="grid gap-2">
                  <FormField label="Rejection reason" htmlFor="lead-response-reject">
                    <Textarea
                      id="lead-response-reject"
                      value={rejectReason}
                      onChange={(event) => setRejectReason(event.target.value)}
                      maxLength={1000}
                    />
                  </FormField>
                  <div className="flex gap-2">
                    <Button type="button" disabled={pending} onClick={() => void reject()}>
                      {pending ? "Rejecting…" : "Confirm reject"}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      disabled={pending}
                      onClick={() => setRejecting(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
          <DialogFooter>
            <DialogCancel>Close</DialogCancel>
            <Button type="submit" disabled={pending || !enquiry.trim()}>
              {pending && !result ? "Generating…" : error && !result ? "Try again" : "Generate draft"}
            </Button>
          </DialogFooter>
        </form>
        <ConfirmDialog
          open={confirmingApprove}
          onOpenChange={(next) => {
            if (!next) setConfirmingApprove(false);
          }}
          title="Approve this response?"
          description="This approves the current response for future sending. Nothing will be sent now."
          confirmLabel={pending ? "Approving…" : "Approve"}
          confirmPending={pending}
          onConfirm={() => void approve()}
        />
        <ConfirmDialog
          open={confirmingSend}
          onOpenChange={(next) => {
            if (!next) setConfirmingSend(false);
          }}
          title="Send this email?"
          description="This will send the approved response to the lead. This is an external action."
          confirmLabel={sending ? "Sending…" : "Send email"}
          confirmPending={sending}
          onConfirm={() => void sendEmail()}
        >
          <dl className="mt-4 grid gap-2">
            <DetailRow label="To" value={lead?.email ?? "—"} muted={!lead?.email} />
            <DetailRow label="Subject" value={EMAIL_SUBJECT} />
            <DetailRow
              label="Message"
              value={
                <span className="whitespace-pre-wrap">{result?.response}</span>
              }
            />
          </dl>
        </ConfirmDialog>
      </DialogContent>
    </Dialog>
  );
}
