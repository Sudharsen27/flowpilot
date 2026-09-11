"use client";

import { type FormEvent, useState } from "react";

import { AiBadge } from "@/components/ai/ai-badge";
import { QualificationStatus } from "@/components/leads/qualification-status";
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
import { qualifyLead } from "@/lib/api/leads";
import type { Lead, LeadQualificationResult } from "@/types/api";

type QualifyLeadDialogProps = {
  open: boolean;
  lead: Lead | null;
  onOpenChange: (open: boolean) => void;
  onCompleted: (result: LeadQualificationResult) => void;
};

function errorMessage(cause: unknown) {
  if (!(cause instanceof ApiError)) {
    return "The enquiry could not be analyzed. Please try again.";
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
  return "The enquiry could not be analyzed. Please try again.";
}

export function QualifyLeadDialog({
  open,
  lead,
  onOpenChange,
  onCompleted,
}: QualifyLeadDialogProps) {
  const [enquiry, setEnquiry] = useState(lead?.notes ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<LeadQualificationResult | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lead || pending) return;
    setError(null);
    setPending(true);
    try {
      const saved = await qualifyLead(lead.id, { enquiry: enquiry.trim() });
      setResult(saved);
      onCompleted(saved);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  const analysis = result?.analysis;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setResult(null);
          setError(null);
          setPending(false);
          setEnquiry(lead?.notes ?? "");
        }
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Analyze with AI</DialogTitle>
          <DialogDescription>
            AI qualification is an analysis of this enquiry. It does not change
            the lead&apos;s CRM status.
          </DialogDescription>
        </DialogHeader>
        {lead ? (
          <p className="text-muted-foreground mt-4 text-sm">
            CRM status for {lead.name}: {lead.status}
          </p>
        ) : null}
        <form className="mt-4 grid gap-4" onSubmit={handleSubmit}>
          <FormField label="Customer enquiry" htmlFor="lead-enquiry" required>
            <Textarea
              id="lead-enquiry"
              value={enquiry}
              onChange={(event) => setEnquiry(event.target.value)}
              maxLength={8000}
              required
            />
          </FormField>
          {pending ? (
            <div className="flex flex-wrap items-center gap-2" role="status">
              <AiBadge label="Processing" />
              <p className="text-muted-foreground text-sm">
                Analyzing enquiry…
              </p>
            </div>
          ) : null}
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          {analysis ? (
            <div className="grid gap-3 text-sm">
              <QualificationStatus status={analysis.qualification} />
              <p>{analysis.summary}</p>
              <p>
                Intent: {analysis.intent.replaceAll("_", " ").toLowerCase()}
              </p>
              <p>
                Self-reported model confidence (not calibrated):{" "}
                {analysis.confidence.toFixed(2)}
              </p>
              {analysis.qualification_reasons.length ? (
                <ul className="list-disc pl-5">
                  {analysis.qualification_reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              ) : null}
              {analysis.missing_information.length ? (
                <div>
                  <p className="font-medium">Missing information</p>
                  <ul className="list-disc pl-5">
                    {analysis.missing_information.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {analysis.buying_signals.length ? (
                <div>
                  <p className="font-medium">Buying signals</p>
                  <ul className="list-disc pl-5">
                    {analysis.buying_signals.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
          <DialogFooter>
            <DialogCancel>Close</DialogCancel>
            <Button type="submit" disabled={pending || !enquiry.trim()}>
              {pending ? "Analyzing…" : error ? "Retry analysis" : "Analyze enquiry"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
