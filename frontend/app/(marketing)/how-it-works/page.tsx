import type { Metadata } from "next";

import {
  MarketingClosing,
  MarketingFrame,
  MarketingPageIntro,
  MarketingRelated,
} from "@/components/marketing/marketing-frame";
import { marketingPageMetadata } from "@/lib/marketing-metadata";

export const metadata: Metadata = marketingPageMetadata({
  title: "How it works",
  description:
    "Capture a lead, review the enquiry, qualify it, draft a response, get human approval, then send only with an explicit action and track follow-ups.",
  path: "/how-it-works",
});

const steps = [
  {
    title: "Capture or select a lead",
    copy: "A visitor can submit the hosted enquiry form when capture is enabled, or someone on the team can create or open an existing lead. Capture does not start the Sales Agent by itself.",
  },
  {
    title: "Review the original enquiry and context",
    copy: "The lead workspace shows the stored enquiry with the contact record. Later qualification and drafts refer back to that text instead of a separate chat transcript.",
  },
  {
    title: "Qualify the lead using AI",
    copy: "Qualification asks the model to structure intent and buying signals from the enquiry. The CRM lead status stays under human control.",
  },
  {
    title: "Prepare a response draft",
    copy: "A Sales Run or the lead-bound Sales Copilot can prepare a customer-facing draft from the enquiry. The draft is saved for review. Nothing is sent at this step.",
  },
  {
    title: "Have a human review and approve it",
    copy: "A person can edit the current text, approve that exact wording, or reject it. Approval means the text is accepted for a possible later send.",
  },
  {
    title: "Send only through the supported explicit action",
    copy: "A separate send action delivers the approved response to the lead's email address. Approval does not send the email, and not every workflow runs automatically.",
  },
  {
    title: "Track follow-ups and activity",
    copy: "The team can schedule, complete, or cancel follow-ups and see overdue work. Organization activity and the lead timeline show what happened, including completed or failed agent executions.",
  },
] as const;

export default function HowItWorksPage() {
  return (
    <MarketingFrame>
      <section className="px-4 pt-20 pb-16 sm:px-6 sm:pt-28 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <MarketingPageIntro
            eyebrow="How it works"
            title="Preparation can be automatic. Sending is not."
            copy="This is the supported path in the current product. Optional workers, such as Sales Agent auto-start or due email follow-ups, stay off until an organization turns them on."
          />
          <ol className="mt-14 grid gap-4">
            {steps.map((step, index) => (
              <li
                key={step.title}
                className="border-border bg-card grid gap-4 rounded-3xl border p-6 sm:grid-cols-[4.5rem_1fr] sm:p-8"
              >
                <span className="bg-foreground text-background flex size-10 items-center justify-center rounded-xl font-mono text-xs font-semibold">
                  0{index + 1}
                </span>
                <div>
                  <h2 className="text-xl font-semibold tracking-tight">{step.title}</h2>
                  <p className="text-muted-foreground mt-3 max-w-3xl leading-7">
                    {step.copy}
                  </p>
                </div>
              </li>
            ))}
          </ol>
          <p className="border-border bg-surface-subtle text-muted-foreground mt-8 rounded-2xl border px-5 py-4 text-sm leading-6">
            Approval does not send the email. A rejected or unapproved draft cannot be sent.
          </p>
          <MarketingRelated
            links={[
              {
                href: "/product",
                label: "Product",
                copy: "See the capabilities that support each step.",
              },
              {
                href: "/use-cases",
                label: "Use cases",
                copy: "Read example situations for enquiries, reviews, and follow-ups.",
              },
            ]}
          />
        </div>
      </section>
      <MarketingClosing
        title="Walk a real enquiry through review before anything is sent."
        copy="Register an organization, then qualify, draft, and approve from the lead you choose."
      />
    </MarketingFrame>
  );
}
