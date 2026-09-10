"use client";

import { type FormEvent, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Textarea } from "@/components/forms/textarea";
import { Button } from "@/components/ui/button";
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
import { generateLeadResponseDraft } from "@/lib/api/leads";
import type { Lead, LeadResponseDraftResult } from "@/types/api";

type DraftLeadResponseDialogProps = {
  open: boolean;
  lead: Lead | null;
  onOpenChange: (open: boolean) => void;
  onCompleted: (result: LeadResponseDraftResult) => void;
};

function errorMessage(cause: unknown) {
  if (!(cause instanceof ApiError)) {
    return "The response draft could not be generated. Please try again.";
  }
  if (cause.status === 503) {
    return "AI provider is not configured.";
  }
  if (cause.status === 422) {
    return "Review the enquiry and correct invalid fields.";
  }
  if (typeof cause.body === "object" && cause.body && "detail" in cause.body) {
    const detail = cause.body.detail;
    if (typeof detail === "string") return detail;
  }
  return "The response draft could not be generated. Please try again.";
}

export function DraftLeadResponseDialog({
  open,
  lead,
  onOpenChange,
  onCompleted,
}: DraftLeadResponseDialogProps) {
  const [enquiry, setEnquiry] = useState(lead?.notes ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<LeadResponseDraftResult | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
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
      onCompleted(saved);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  async function copyDraft() {
    if (!result?.response) return;
    await navigator.clipboard.writeText(result.response);
    setCopied(true);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setResult(null);
          setError(null);
          setPending(false);
          setCopied(false);
          setEnquiry(lead?.notes ?? "");
        }
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Draft response</DialogTitle>
          <DialogDescription>
            This is an AI-generated draft. Nothing has been sent.
          </DialogDescription>
        </DialogHeader>
        {lead ? (
          <p className="text-muted-foreground mt-4 text-sm">
            CRM status for {lead.name}: {lead.status}
          </p>
        ) : null}
        <form className="mt-4 grid gap-4" onSubmit={handleSubmit}>
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
            <p role="status" className="text-muted-foreground text-sm">
              Generating draft…
            </p>
          ) : null}
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          {result?.response ? (
            <div className="grid gap-2">
              <p className="text-sm font-medium">AI draft</p>
              <p className="border-border bg-muted/40 rounded-md border p-3 text-sm leading-6 whitespace-pre-wrap">
                {result.response}
              </p>
              <Button type="button" variant="outline" size="sm" onClick={() => void copyDraft()}>
                {copied ? "Copied" : "Copy draft"}
              </Button>
            </div>
          ) : null}
          <DialogFooter>
            <DialogCancel>Close</DialogCancel>
            <Button type="submit" disabled={pending || !enquiry.trim()}>
              {pending ? "Generating…" : error ? "Try again" : "Generate draft"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
