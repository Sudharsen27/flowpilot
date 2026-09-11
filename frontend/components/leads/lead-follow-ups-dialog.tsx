"use client";

import { type FormEvent, useEffect, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
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
import { ApiError } from "@/lib/api/client";
import {
  cancelLeadFollowUp,
  completeLeadFollowUp,
  createLeadFollowUp,
  getLeadFollowUps,
  updateLeadFollowUp,
} from "@/lib/api/leads";
import type { Lead, LeadFollowUp, LeadFollowUpType } from "@/types/api";

type LeadFollowUpsDialogProps = {
  open: boolean;
  lead: Lead | null;
  onOpenChange: (open: boolean) => void;
  /** Called after a follow-up is created, rescheduled, completed or cancelled. */
  onChanged?: () => void;
};

const typeLabels: Record<LeadFollowUpType, string> = {
  EMAIL_FOLLOW_UP: "Email follow-up",
  MANUAL_FOLLOW_UP: "Manual follow-up",
};

function errorMessage(cause: unknown) {
  if (!(cause instanceof ApiError)) {
    return "The request could not be completed. Please try again.";
  }
  if (cause.status === 401) {
    return "Your session expired. Sign in again.";
  }
  if (cause.status === 403) {
    return "You do not have permission to manage follow-ups.";
  }
  if (cause.status === 404) {
    return "This follow-up could not be found.";
  }
  if (cause.status === 409) {
    return "This follow-up changed. Refresh and review the latest status.";
  }
  if (cause.status === 422) {
    return "Review the due date, type, and email body, then try again.";
  }
  if (typeof cause.body === "object" && cause.body && "detail" in cause.body) {
    const detail = cause.body.detail;
    if (typeof detail === "string") return detail;
  }
  return "The request could not be completed. Please try again.";
}

function formatDue(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : new Intl.DateTimeFormat("en", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

function toLocalInput(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromLocalInput(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

export function LeadFollowUpsDialog({
  open,
  lead,
  onOpenChange,
  onChanged,
}: LeadFollowUpsDialogProps) {
  const [items, setItems] = useState<LeadFollowUp[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [type, setType] = useState<LeadFollowUpType>("EMAIL_FOLLOW_UP");
  const [dueAt, setDueAt] = useState("");
  const [notes, setNotes] = useState("");
  const [bodyText, setBodyText] = useState("");
  const [reschedulingId, setReschedulingId] = useState<string | null>(null);
  const [rescheduleDue, setRescheduleDue] = useState("");
  const [editingBody, setEditingBody] = useState("");
  const [editingNotes, setEditingNotes] = useState("");
  const [confirmingCancelId, setConfirmingCancelId] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !lead) return;
    let cancelled = false;
    void getLeadFollowUps(lead.id)
      .then((page) => {
        if (!cancelled) setItems(page.items);
      })
      .catch((cause) => {
        if (!cancelled) setError(errorMessage(cause));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [lead, open]);

  async function refresh() {
    if (!lead) return;
    const page = await getLeadFollowUps(lead.id);
    setItems(page.items);
    // Let callers reload their own view from the backend rather than guessing.
    onChanged?.();
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lead || pending) return;
    const iso = fromLocalInput(dueAt);
    if (!iso) {
      setError("A valid due date and time is required.");
      return;
    }
    if (type === "EMAIL_FOLLOW_UP" && !bodyText.trim()) {
      setError("Email body is required for email follow-ups.");
      return;
    }
    setError(null);
    setPending(true);
    try {
      await createLeadFollowUp(lead.id, {
        due_at: iso,
        type,
        notes: notes.trim() || null,
        ...(type === "EMAIL_FOLLOW_UP" ? { body_text: bodyText.trim() } : {}),
      });
      setDueAt("");
      setNotes("");
      setBodyText("");
      await refresh();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  async function handleReschedule(followUp: LeadFollowUp) {
    if (!lead || pending) return;
    const iso = fromLocalInput(rescheduleDue);
    if (!iso) {
      setError("A valid due date and time is required.");
      return;
    }
    if (followUp.type === "EMAIL_FOLLOW_UP") {
      const trimmed = editingBody.trim();
      if (!trimmed && followUp.body_text) {
        setError("Email body is required for email follow-ups.");
        return;
      }
    }
    setError(null);
    setPending(true);
    try {
      await updateLeadFollowUp(lead.id, followUp.id, {
        expected_revision: followUp.revision,
        due_at: iso,
        ...(followUp.type === "EMAIL_FOLLOW_UP" && editingBody.trim()
          ? { body_text: editingBody.trim() }
          : {}),
        ...(followUp.type === "MANUAL_FOLLOW_UP"
          ? { notes: editingNotes.trim() || null }
          : {}),
      });
      setReschedulingId(null);
      await refresh();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  async function handleComplete(followUp: LeadFollowUp) {
    if (!lead || pending) return;
    setError(null);
    setPending(true);
    try {
      await completeLeadFollowUp(lead.id, followUp.id, {
        expected_revision: followUp.revision,
      });
      await refresh();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  async function handleCancel(followUp: LeadFollowUp) {
    if (!lead || pending) return;
    setConfirmingCancelId(null);
    setError(null);
    setPending(true);
    try {
      await cancelLeadFollowUp(lead.id, followUp.id, {
        expected_revision: followUp.revision,
      });
      await refresh();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Follow-ups</DialogTitle>
          <DialogDescription>
            Schedule a reminder for this lead. Due follow-ups are not sent
            automatically.
          </DialogDescription>
        </DialogHeader>
        {lead ? (
          <p className="text-muted-foreground mt-4 text-sm">For {lead.name}</p>
        ) : null}
        <form className="mt-4 grid gap-4" onSubmit={handleCreate}>
          <FormField label="Type" htmlFor="follow-up-type">
            <Select
              id="follow-up-type"
              value={type}
              onChange={(event) => setType(event.target.value as LeadFollowUpType)}
            >
              <option value="EMAIL_FOLLOW_UP">Email follow-up</option>
              <option value="MANUAL_FOLLOW_UP">Manual follow-up</option>
            </Select>
          </FormField>
          <FormField label="Due date and time" htmlFor="follow-up-due" required>
            <Input
              id="follow-up-due"
              type="datetime-local"
              value={dueAt}
              onChange={(event) => setDueAt(event.target.value)}
              required
            />
          </FormField>
          {type === "EMAIL_FOLLOW_UP" ? (
            <FormField label="Email body" htmlFor="follow-up-body" required>
              <Textarea
                id="follow-up-body"
                value={bodyText}
                onChange={(event) => setBodyText(event.target.value)}
                maxLength={8000}
                required
              />
            </FormField>
          ) : (
            <FormField label="Notes" htmlFor="follow-up-notes">
              <Textarea
                id="follow-up-notes"
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                maxLength={4000}
              />
            </FormField>
          )}
          {loading ? (
            <p role="status" className="text-muted-foreground text-sm">
              Loading follow-ups…
            </p>
          ) : null}
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          <div>
            <Button
              type="submit"
              disabled={
                pending ||
                !dueAt ||
                (type === "EMAIL_FOLLOW_UP" && !bodyText.trim())
              }
            >
              {pending ? "Saving…" : "Create follow-up"}
            </Button>
          </div>
        </form>
        <div className="mt-6 grid gap-3">
          {!loading && items.length === 0 ? (
            <p className="text-muted-foreground text-sm">No follow-ups yet.</p>
          ) : null}
          {items.map((item) => (
            <article
              key={item.id}
              className="border-border rounded-md border p-3 text-sm"
            >
              <p className="font-medium">
                {item.is_overdue ? "OVERDUE" : item.status}
              </p>
              <p>{formatDue(item.due_at)}</p>
              <p className="text-muted-foreground">{typeLabels[item.type]}</p>
              {item.type === "EMAIL_FOLLOW_UP" ? (
                <div className="mt-2">
                  <p className="text-muted-foreground text-xs font-medium uppercase">
                    Email body
                  </p>
                  {item.body_text ? (
                    <p className="mt-1 whitespace-pre-wrap">{item.body_text}</p>
                  ) : (
                    <p className="text-muted-foreground mt-1">No email body stored.</p>
                  )}
                </div>
              ) : item.notes ? (
                <p className="mt-1">{item.notes}</p>
              ) : null}
              {item.status === "PENDING" ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={pending}
                    onClick={() => {
                      setReschedulingId(item.id);
                      setRescheduleDue(toLocalInput(item.due_at));
                      setEditingBody(item.body_text ?? "");
                      setEditingNotes(item.notes ?? "");
                    }}
                  >
                    Reschedule
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    disabled={pending}
                    onClick={() => void handleComplete(item)}
                  >
                    Complete
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={pending}
                    onClick={() => setConfirmingCancelId(item.id)}
                  >
                    Cancel follow-up
                  </Button>
                </div>
              ) : null}
              {reschedulingId === item.id ? (
                <div className="mt-3 grid gap-2">
                  <FormField
                    label="New due date and time"
                    htmlFor={`follow-up-reschedule-${item.id}`}
                    required
                  >
                    <Input
                      id={`follow-up-reschedule-${item.id}`}
                      type="datetime-local"
                      value={rescheduleDue}
                      onChange={(event) => setRescheduleDue(event.target.value)}
                      required
                    />
                  </FormField>
                  {item.type === "EMAIL_FOLLOW_UP" ? (
                    <FormField
                      label="Edit email body"
                      htmlFor={`follow-up-edit-body-${item.id}`}
                    >
                      <Textarea
                        id={`follow-up-edit-body-${item.id}`}
                        value={editingBody}
                        onChange={(event) => setEditingBody(event.target.value)}
                        maxLength={8000}
                      />
                    </FormField>
                  ) : (
                    <FormField
                      label="Notes"
                      htmlFor={`follow-up-edit-notes-${item.id}`}
                    >
                      <Textarea
                        id={`follow-up-edit-notes-${item.id}`}
                        value={editingNotes}
                        onChange={(event) => setEditingNotes(event.target.value)}
                        maxLength={4000}
                      />
                    </FormField>
                  )}
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      size="sm"
                      disabled={pending || !rescheduleDue}
                      onClick={() => void handleReschedule(item)}
                    >
                      Save
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={pending}
                      onClick={() => setReschedulingId(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : null}
            </article>
          ))}
        </div>
        <DialogFooter>
          <DialogCancel>Close</DialogCancel>
        </DialogFooter>
        <ConfirmDialog
          open={Boolean(confirmingCancelId)}
          onOpenChange={(next) => {
            if (!next) setConfirmingCancelId(null);
          }}
          title="Cancel this follow-up?"
          description="The record will be kept as cancelled. It will not be deleted."
          cancelLabel="Keep follow-up"
          confirmLabel="Cancel follow-up"
          variant="destructive"
          confirmPending={pending}
          onConfirm={() => {
            const target = items.find((item) => item.id === confirmingCancelId);
            if (target) void handleCancel(target);
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
