"use client";

import { type FormEvent, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
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
import { createLead, updateLead } from "@/lib/api/leads";
import type { Lead, LeadCreateRequest, LeadSource, LeadStatus } from "@/types/api";

type LeadFormDialogProps = {
  open: boolean;
  lead?: Lead | null;
  onOpenChange: (open: boolean) => void;
  onSaved: (lead: Lead) => void;
};

const emptyForm = {
  name: "",
  email: "",
  phone: "",
  company: "",
  source: "MANUAL" as LeadSource,
  status: "NEW" as LeadStatus,
  notes: "",
};

function optional(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function formFromLead(lead?: Lead | null) {
  if (!lead) return emptyForm;
  return {
    name: lead.name,
    email: lead.email ?? "",
    phone: lead.phone ?? "",
    company: lead.company ?? "",
    source: lead.source,
    status: lead.status,
    notes: lead.notes ?? "",
  };
}

export function LeadFormDialog({
  open,
  lead,
  onOpenChange,
  onSaved,
}: LeadFormDialogProps) {
  const isEdit = Boolean(lead);
  const [form, setForm] = useState(() => formFromLead(lead));
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setError(null);
    setPending(true);
    const payload: LeadCreateRequest = {
      name: form.name.trim(),
      email: optional(form.email),
      phone: optional(form.phone),
      company: optional(form.company),
      source: form.source,
      status: form.status,
      notes: optional(form.notes),
    };
    try {
      const saved = lead
        ? await updateLead(lead.id, payload)
        : await createLead(payload);
      onSaved(saved);
      onOpenChange(false);
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 422
          ? "Review the lead details and correct invalid fields."
          : "The lead could not be saved. Please try again.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit lead" : "Create lead"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update this organization's lead record. Status is a pipeline field, not an AI qualification result."
              : "Add a lead to this organization. AI extraction and scoring are not part of this screen."}
          </DialogDescription>
        </DialogHeader>
        <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
          <FormField label="Name" htmlFor="lead-name" required>
            <Input
              id="lead-name"
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
              maxLength={200}
              autoFocus
              required
            />
          </FormField>
          <FormField label="Email" htmlFor="lead-email">
            <Input
              id="lead-email"
              type="email"
              value={form.email}
              onChange={(event) =>
                setForm((current) => ({ ...current, email: event.target.value }))
              }
              maxLength={320}
            />
          </FormField>
          <FormField label="Phone" htmlFor="lead-phone">
            <Input
              id="lead-phone"
              value={form.phone}
              onChange={(event) =>
                setForm((current) => ({ ...current, phone: event.target.value }))
              }
              maxLength={40}
            />
          </FormField>
          <FormField label="Company" htmlFor="lead-company">
            <Input
              id="lead-company"
              value={form.company}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  company: event.target.value,
                }))
              }
              maxLength={200}
            />
          </FormField>
          <FormField label="Source" htmlFor="lead-source-field" required>
            <Select
              id="lead-source-field"
              value={form.source}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  source: event.target.value as LeadSource,
                }))
              }
            >
              <option value="MANUAL">Manual</option>
              <option value="WEBSITE">Website</option>
              <option value="EMAIL">Email</option>
              <option value="CHAT">Chat</option>
              <option value="API">API</option>
              <option value="IMPORT">Import</option>
            </Select>
          </FormField>
          <FormField label="Status" htmlFor="lead-status-field" required>
            <Select
              id="lead-status-field"
              value={form.status}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  status: event.target.value as LeadStatus,
                }))
              }
            >
              <option value="NEW">New</option>
              <option value="CONTACTED">Contacted</option>
              <option value="QUALIFIED">Qualified</option>
              <option value="UNQUALIFIED">Unqualified</option>
              <option value="CONVERTED">Converted</option>
            </Select>
          </FormField>
          <FormField label="Notes" htmlFor="lead-notes">
            <Textarea
              id="lead-notes"
              value={form.notes}
              onChange={(event) =>
                setForm((current) => ({ ...current, notes: event.target.value }))
              }
              maxLength={4000}
            />
          </FormField>
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <DialogCancel>Cancel</DialogCancel>
            <Button type="submit" disabled={pending || !form.name.trim()}>
              {pending ? "Saving…" : isEdit ? "Save changes" : "Create lead"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
