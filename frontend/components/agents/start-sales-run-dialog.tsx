"use client";

import { type FormEvent, useState } from "react";

import { AiBadge } from "@/components/ai/ai-badge";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
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
import { startSalesRun } from "@/lib/api/sales-runs";
import type { SalesRun } from "@/types/api";

type StartSalesRunDialogProps = {
  open: boolean;
  agentId: string;
  onOpenChange: (open: boolean) => void;
  onCompleted: (result: SalesRun) => void;
};

function errorMessage(cause: unknown) {
  if (!(cause instanceof ApiError)) {
    return "The sales run could not be started. Please try again.";
  }
  if (cause.status === 409 && isRecord(cause.body) && typeof cause.body.detail === "string") {
    return cause.body.detail;
  }
  if (cause.status === 503) {
    return "AI provider is not configured.";
  }
  if (cause.status === 422) {
    return "Review the enquiry and lead fields.";
  }
  if (isRecord(cause.body) && typeof cause.body.detail === "string") {
    return cause.body.detail;
  }
  if (cause.status === 400 && isRecord(cause.body) && typeof cause.body.detail === "string") {
    return cause.body.detail;
  }
  return "The sales run could not be started. Please try again.";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function StartSalesRunDialog({
  open,
  agentId,
  onOpenChange,
  onCompleted,
}: StartSalesRunDialogProps) {
  const [enquiry, setEnquiry] = useState("");
  const [leadId, setLeadId] = useState("");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);

  const creatingLead = !leadId.trim();
  const nameRequired = creatingLead && !email.trim();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const trimmedEnquiry = enquiry.trim();
    if (!trimmedEnquiry) {
      setFieldError("Enquiry is required.");
      return;
    }
    if (nameRequired && !name.trim()) {
      setFieldError("Name is required to create a lead.");
      return;
    }
    setFieldError(null);
    setError(null);
    setPending(true);
    try {
      const result = await startSalesRun(agentId, {
        enquiry: trimmedEnquiry,
        lead_id: leadId.trim() || undefined,
        email: email.trim() || undefined,
        name: name.trim() || undefined,
      });
      setEnquiry("");
      setLeadId("");
      setEmail("");
      setName("");
      onCompleted(result);
      onOpenChange(false);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (pending) return;
        if (!next) {
          setError(null);
          setFieldError(null);
        }
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-2">
            <DialogTitle>Start Sales Run</DialogTitle>
            <AiBadge label="Agent" />
          </div>
          <DialogDescription>
            This Sales Agent will qualify the enquiry and prepare a response for
            your review. It will not send the email automatically.
          </DialogDescription>
        </DialogHeader>
        <form className="mt-4 grid gap-4" onSubmit={handleSubmit}>
          <FormField label="Enquiry" htmlFor="sales-run-enquiry" required error={fieldError}>
            <Textarea
              id="sales-run-enquiry"
              value={enquiry}
              onChange={(event) => setEnquiry(event.target.value)}
              maxLength={8000}
              disabled={pending}
              aria-invalid={fieldError ? true : undefined}
            />
          </FormField>
          <FormField label="Lead ID" htmlFor="sales-run-lead-id" description="Optional. Use an existing lead.">
            <Input
              id="sales-run-lead-id"
              value={leadId}
              onChange={(event) => setLeadId(event.target.value)}
              disabled={pending}
            />
          </FormField>
          <FormField label="Email" htmlFor="sales-run-email" description="Optional. Matches an existing lead or is stored on a new lead.">
            <Input
              id="sales-run-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              disabled={pending}
            />
          </FormField>
          <FormField
            label="Name"
            htmlFor="sales-run-name"
            required={nameRequired}
            description="Required when creating a new lead."
          >
            <Input
              id="sales-run-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={pending}
            />
          </FormField>
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <DialogCancel>Close</DialogCancel>
            <Button type="submit" disabled={pending}>
              {pending ? "Starting…" : "Start sales run"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
