"use client";

import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  CheckCircle2,
  CircleDot,
  FileText,
  LockKeyhole,
  Mail,
  Play,
  RotateCcw,
  Sparkles,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/forms/textarea";
import {
  DEMO_LEAD,
  DEMO_QUALIFICATION,
  DEMO_RESPONSE,
} from "@/components/marketing/demo-fixtures";
import { cn } from "@/lib/utils";

const DEMO_STEPS = [
  "New enquiry",
  "Lead context",
  "AI qualification",
  "Response draft",
  "Human review",
  "Sending boundary",
  "Summary",
] as const;

const NEXT_LABELS: Record<number, string> = {
  0: "View lead context",
  1: "Continue to qualification",
  2: "Continue to sample draft",
  3: "Continue to review",
  4: "Continue to sending boundary",
  5: "View workflow summary",
};

function SampleLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="border-info/25 bg-info/5 text-info-text inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium">
      <CircleDot className="size-3" aria-hidden="true" />
      {children}
    </span>
  );
}

function LeadSummary() {
  return (
    <aside className="border-border bg-surface-subtle grid content-start gap-5 rounded-lg border p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <span className="bg-background text-muted-foreground flex size-10 shrink-0 items-center justify-center rounded-lg border">
          <UserRound className="size-4" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <p className="text-muted-foreground text-[0.6875rem] font-medium uppercase">
            Sample lead
          </p>
          <h3 className="mt-1 text-lg leading-tight font-semibold">
            {DEMO_LEAD.name}
          </h3>
          <p className="text-muted-foreground mt-1 text-sm">
            {DEMO_LEAD.company}
          </p>
        </div>
      </div>

      <dl className="grid gap-3 border-t pt-4">
        <div className="flex items-center justify-between gap-3">
          <dt className="text-muted-foreground text-xs">Role</dt>
          <dd className="text-right text-sm font-medium">{DEMO_LEAD.role}</dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt className="text-muted-foreground text-xs">CRM status</dt>
          <dd className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium">
            <span
              className="bg-info size-1.5 rounded-full"
              aria-hidden="true"
            />
            {DEMO_LEAD.crmStatus}
          </dd>
        </div>
      </dl>

      <p className="text-muted-foreground border-t pt-4 text-xs leading-5">
        CRM status stays New throughout this sample workflow.
      </p>
    </aside>
  );
}

export function InteractiveProductDemo() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const [qualificationComplete, setQualificationComplete] = useState(false);
  const [draftGenerated, setDraftGenerated] = useState(false);
  const [draftText, setDraftText] = useState(DEMO_RESPONSE);
  const [approved, setApproved] = useState(false);

  const canContinue =
    step === 0 ||
    step === 1 ||
    (step === 2 && qualificationComplete) ||
    (step === 3 && draftGenerated) ||
    (step === 4 && approved) ||
    step === 5;

  function restartDemo() {
    setStep(0);
    setQualificationComplete(false);
    setDraftGenerated(false);
    setDraftText(DEMO_RESPONSE);
    setApproved(false);
  }

  function continueDemo() {
    setStep((current) => Math.min(current + 1, DEMO_STEPS.length - 1));
  }

  function renderStep() {
    switch (step) {
      case 0:
        return (
          <div className="grid gap-4">
            <div className="flex items-center gap-2">
              <span className="bg-info/10 text-info-text flex size-9 items-center justify-center rounded-lg">
                <Mail className="size-4" aria-hidden="true" />
              </span>
              <div>
                <p className="text-sm font-semibold">A new enquiry arrives</p>
                <p className="text-muted-foreground text-xs">
                  Website enquiry · sample
                </p>
              </div>
            </div>
            <blockquote className="border-border bg-background rounded-md border p-4 text-sm leading-6">
              “{DEMO_LEAD.enquiry}”
            </blockquote>
            <p className="text-muted-foreground text-xs leading-5">
              This fictional enquiry is displayed locally. It has not been
              submitted to FlowPilot.
            </p>
          </div>
        );
      case 1:
        return (
          <div className="grid gap-5">
            <div>
              <h3 className="text-sm font-semibold">Lead context</h3>
              <p className="text-muted-foreground mt-1 text-xs leading-5">
                The original enquiry and CRM status remain separate from any AI
                assessment.
              </p>
            </div>
            <div className="grid gap-3">
              <div className="flex items-center gap-2 text-xs font-medium">
                <Building2
                  className="text-muted-foreground size-4"
                  aria-hidden="true"
                />
                {DEMO_LEAD.company} · {DEMO_LEAD.role}
              </div>
              <blockquote className="border-border bg-surface-subtle rounded-md border p-3 text-sm leading-6">
                {DEMO_LEAD.enquiry}
              </blockquote>
            </div>
            <div>
              <h4 className="text-muted-foreground text-xs font-semibold uppercase">
                Sample activity history
              </h4>
              <ol className="mt-3 grid gap-3">
                {DEMO_LEAD.activity.map((item) => (
                  <li key={item} className="flex items-center gap-2.5 text-sm">
                    <CheckCircle2
                      className="text-success-text size-4 shrink-0"
                      aria-hidden="true"
                    />
                    {item}
                  </li>
                ))}
                <li className="text-muted-foreground flex items-center gap-2.5 text-sm">
                  <CircleDot className="size-4 shrink-0" aria-hidden="true" />
                  No AI or review actions yet
                </li>
              </ol>
            </div>
          </div>
        );
      case 2:
        return (
          <div className="grid gap-4">
            <div className="flex items-start gap-3">
              <span className="bg-ai/10 text-ai-text flex size-9 shrink-0 items-center justify-center rounded-lg">
                <Sparkles className="size-4" aria-hidden="true" />
              </span>
              <div>
                <h3 className="text-sm font-semibold">Sample qualification</h3>
                <p className="text-muted-foreground mt-1 text-xs leading-5">
                  Click to reveal fixed sample results. This does not call an AI
                  provider.
                </p>
              </div>
            </div>
            {qualificationComplete ? (
              <div
                className="border-ai-border bg-ai/5 grid gap-4 rounded-md border p-4"
                aria-live="polite"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <SampleLabel>Simulated AI results</SampleLabel>
                  <span className="text-muted-foreground text-xs">
                    {DEMO_QUALIFICATION.confidence} illustrative sample score
                  </span>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Intent</p>
                  <p className="mt-1 text-sm font-medium">
                    {DEMO_QUALIFICATION.intent}
                  </p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="text-muted-foreground text-xs">
                      Buying signals
                    </p>
                    <ul className="mt-1.5 grid gap-1 text-sm">
                      {DEMO_QUALIFICATION.buyingSignals.map((signal) => (
                        <li key={signal} className="flex gap-2">
                          <Check
                            className="text-success-text mt-0.5 size-3.5 shrink-0"
                            aria-hidden="true"
                          />
                          {signal}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="text-muted-foreground text-xs">
                      Missing information
                    </p>
                    <ul className="mt-1.5 grid gap-1 text-sm">
                      {DEMO_QUALIFICATION.missingInformation.map((item) => (
                        <li key={item} className="text-muted-foreground">
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <p className="text-muted-foreground border-t pt-3 text-xs leading-5">
                  Illustrative only. No CRM status or real record was changed.
                </p>
              </div>
            ) : (
              <Button
                type="button"
                onClick={() => setQualificationComplete(true)}
              >
                <Sparkles aria-hidden="true" />
                Run Sample Qualification
              </Button>
            )}
          </div>
        );
      case 3:
        return (
          <div className="grid gap-4">
            <div className="flex items-start gap-3">
              <span className="bg-info/10 text-info-text flex size-9 shrink-0 items-center justify-center rounded-lg">
                <FileText className="size-4" aria-hidden="true" />
              </span>
              <div>
                <h3 className="text-sm font-semibold">Response draft</h3>
                <p className="text-muted-foreground mt-1 text-xs leading-5">
                  Prepare editable sample text locally. It will not be saved or
                  sent.
                </p>
              </div>
            </div>
            {draftGenerated ? (
              <div className="grid gap-2" aria-live="polite">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label
                    className="text-muted-foreground text-xs font-medium"
                    htmlFor="demo-response-draft"
                  >
                    Sample email text
                  </label>
                  <SampleLabel>Local sample draft</SampleLabel>
                </div>
                <Textarea
                  id="demo-response-draft"
                  aria-label="Sample response draft"
                  value={draftText}
                  onChange={(event) => setDraftText(event.target.value)}
                  rows={9}
                  maxLength={2000}
                  className="bg-background min-h-56 resize-y text-sm leading-6"
                />
                <p className="text-muted-foreground text-xs">
                  Editing here changes only this browser demo.
                </p>
              </div>
            ) : (
              <Button type="button" onClick={() => setDraftGenerated(true)}>
                <FileText aria-hidden="true" />
                Generate Sample Draft
              </Button>
            )}
          </div>
        );
      case 4:
        return (
          <div className="grid gap-4">
            <div>
              <h3 className="text-sm font-semibold">Human review</h3>
              <p className="text-muted-foreground mt-1 text-xs leading-5">
                Review or edit the local sample before simulating approval.
              </p>
            </div>
            <Textarea
              aria-label="Review sample response"
              value={draftText}
              onChange={(event) => setDraftText(event.target.value)}
              rows={8}
              maxLength={2000}
              className="bg-background min-h-52 resize-y text-sm leading-6"
            />
            {approved ? (
              <div
                className="border-success/25 bg-success/5 flex items-start gap-2 rounded-md border p-3"
                role="status"
              >
                <CheckCircle2
                  className="text-success-text mt-0.5 size-4 shrink-0"
                  aria-hidden="true"
                />
                <div>
                  <p className="text-sm font-semibold">Approved in demo</p>
                  <p className="text-muted-foreground mt-1 text-xs leading-5">
                    This simulated approval changed only local demo state.
                  </p>
                </div>
              </div>
            ) : (
              <Button type="button" onClick={() => setApproved(true)}>
                <Check aria-hidden="true" />
                Approve Sample Draft
              </Button>
            )}
          </div>
        );
      case 5:
        return (
          <div className="grid gap-4">
            <div className="bg-success/5 border-success/25 flex items-start gap-3 rounded-md border p-4">
              <CheckCircle2
                className="text-success-text mt-0.5 size-5 shrink-0"
                aria-hidden="true"
              />
              <div>
                <h3 className="text-sm font-semibold">
                  Ready for a real sending workflow
                </h3>
                <p className="text-muted-foreground mt-1 text-sm leading-6">
                  Approval does not automatically send email. In FlowPilot,
                  sending is a separate, explicit human action.
                </p>
              </div>
            </div>
            <div className="border-border bg-surface-subtle flex items-start gap-3 rounded-md border p-4">
              <LockKeyhole
                className="text-muted-foreground mt-0.5 size-4 shrink-0"
                aria-hidden="true"
              />
              <p className="text-muted-foreground text-xs leading-5">
                This demo never sends email, calls a send endpoint, or claims
                real delivery. No worker or provider runs here.
              </p>
            </div>
          </div>
        );
      default:
        return (
          <div className="grid gap-4">
            <div className="flex items-start gap-3">
              <span className="bg-success/10 text-success-text flex size-9 shrink-0 items-center justify-center rounded-lg">
                <CheckCircle2 className="size-4" aria-hidden="true" />
              </span>
              <div>
                <h3 className="text-sm font-semibold">
                  Sample workflow complete
                </h3>
                <p className="text-muted-foreground mt-1 text-xs leading-5">
                  The walkthrough is complete. All results and decisions below
                  were simulated locally.
                </p>
              </div>
            </div>
            <ol className="divide-border divide-y">
              {[
                ["Sample lead", `${DEMO_LEAD.name} · ${DEMO_LEAD.company}`],
                ["CRM status", "New (unchanged)"],
                ["Qualification", "Simulated sample result shown"],
                ["Review", "Approved in demo"],
                ["Email", "Not sent · no delivery claimed"],
              ].map(([label, value]) => (
                <li
                  key={label}
                  className="flex flex-wrap justify-between gap-2 py-3 text-sm"
                >
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-medium">{value}</span>
                </li>
              ))}
            </ol>
            <p className="text-muted-foreground text-xs leading-5">
              This fictional walkthrough has not created or changed a FlowPilot
              record.
            </p>
          </div>
        );
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        className={buttonVariants({
          variant: "outline",
          size: "lg",
          className: "h-11 px-4 text-base",
        })}
      >
        <Play aria-hidden="true" />
        Play Product Demo
      </DialogTrigger>
      <DialogContent className="max-h-[calc(100dvh-2rem)] max-w-5xl overflow-y-auto p-0 sm:p-0">
        <div className="grid gap-5 p-4 sm:gap-6 sm:p-7">
          <DialogHeader className="gap-3 pr-10 sm:gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="bg-foreground text-background flex size-8 items-center justify-center rounded-md">
                <Sparkles className="size-4" aria-hidden="true" />
              </span>
              <span className="text-muted-foreground text-xs font-medium">
                FlowPilot · Sample workspace
              </span>
              <SampleLabel>Fictional data</SampleLabel>
            </div>
            <div>
              <DialogTitle className="text-xl sm:text-2xl">
                Interactive product demo
              </DialogTitle>
              <DialogDescription className="mt-1.5 max-w-2xl">
                Explore a sample lead workflow. Every result is local and
                simulated; no account or network calls are involved.
              </DialogDescription>
            </div>
            <div className="grid gap-2" aria-label="Demo progress">
              <div
                className="bg-muted h-1.5 overflow-hidden rounded-full"
                role="progressbar"
                aria-label="Demo workflow progress"
                aria-valuemin={1}
                aria-valuemax={DEMO_STEPS.length}
                aria-valuenow={step + 1}
              >
                <div
                  className="bg-ai h-full rounded-full transition-[width] duration-300 motion-reduce:transition-none"
                  style={{
                    width: `${((step + 1) / DEMO_STEPS.length) * 100}%`,
                  }}
                />
              </div>
              <div className="text-muted-foreground flex justify-between gap-3 text-xs">
                <span>
                  Step {step + 1} of {DEMO_STEPS.length}
                </span>
                <span className="text-foreground text-right font-medium">
                  {DEMO_STEPS[step]}
                </span>
              </div>
            </div>
          </DialogHeader>

          <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(14rem,0.72fr)_minmax(0,1.28fr)]">
            <LeadSummary />
            <section
              key={step}
              className="border-border bg-card motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-right-1 min-w-0 rounded-lg border p-4 motion-safe:duration-200 sm:p-5"
              aria-label={DEMO_STEPS[step]}
            >
              {renderStep()}
            </section>
          </div>

          <footer className="border-border flex flex-col-reverse gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col-reverse gap-2 sm:flex-row">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setOpen(false)}
              >
                Close demo
              </Button>
              {step === DEMO_STEPS.length - 1 ? (
                <Link
                  href="/contact"
                  className={cn(buttonVariants({ variant: "outline" }))}
                >
                  Request a real demo
                </Link>
              ) : null}
            </div>
            <div className="flex justify-between gap-2 sm:justify-end">
              {step > 0 && step < DEMO_STEPS.length - 1 ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setStep((current) => current - 1)}
                >
                  <ArrowLeft aria-hidden="true" />
                  Back
                </Button>
              ) : null}
              {step < DEMO_STEPS.length - 1 ? (
                <Button
                  type="button"
                  disabled={!canContinue}
                  onClick={continueDemo}
                >
                  {NEXT_LABELS[step]}
                  <ArrowRight aria-hidden="true" />
                </Button>
              ) : (
                <Button type="button" onClick={restartDemo}>
                  <RotateCcw aria-hidden="true" />
                  Restart Demo
                </Button>
              )}
            </div>
          </footer>
        </div>
      </DialogContent>
    </Dialog>
  );
}
