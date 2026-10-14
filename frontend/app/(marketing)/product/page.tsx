import {
  Activity,
  Bot,
  FileCheck2,
  Inbox,
  MailCheck,
  Sparkles,
  Users,
} from "lucide-react";
import type { Metadata } from "next";

import {
  MarketingClosing,
  MarketingFrame,
  MarketingPageIntro,
  MarketingRelated,
} from "@/components/marketing/marketing-frame";
import { marketingPageMetadata } from "@/lib/marketing-metadata";

export const metadata: Metadata = marketingPageMetadata({
  title: "Product",
  description:
    "Explore FlowPilot product capabilities: lead context, AI qualification, Sales Copilot drafts, human approval, explicit email sending, follow-ups, and activity visibility.",
  path: "/product",
});

const capabilities = [
  {
    icon: Users,
    title: "Lead and customer context",
    copy: "Each lead keeps its contact details, original enquiry, CRM status, qualification, response history, and follow-ups together. AI qualification does not rewrite the CRM status.",
  },
  {
    icon: Sparkles,
    title: "AI lead qualification",
    copy: "Qualification reads the stored enquiry and records intent, buying signals, and missing information. It is analysis for the team, not an automatic change to the lead's pipeline status.",
  },
  {
    icon: Bot,
    title: "Lead-bound Sales Copilot",
    copy: "A Copilot run is tied to the lead you selected. It uses that lead's stored enquiry to qualify and draft. It does not send email from the Copilot.",
  },
  {
    icon: FileCheck2,
    title: "Response drafting and human approval",
    copy: "Drafts are prepared for review. A person can edit, approve, or reject the current text. Approving a draft records that decision. It does not send the email.",
  },
  {
    icon: MailCheck,
    title: "Explicit email sending",
    copy: "Sending is a separate action. FlowPilot uses the lead's email address and the approved response text. The sender and body are not chosen by the visitor on the marketing site.",
  },
  {
    icon: Inbox,
    title: "Sales Runs and follow-up operations",
    copy: "A Sales Run can qualify a lead and prepare a draft, then wait for review. Follow-ups can be scheduled, completed, or cancelled, and overdue reminders stay visible. Due email follow-ups are sent only when that worker is enabled.",
  },
  {
    icon: Activity,
    title: "Activity and execution visibility",
    copy: "Organization activity records operational events. Lead timelines can show completed and failed agent executions, and whether Sales Agent auto-start was skipped or failed. Those outcomes are not pending approvals.",
  },
] as const;

export default function ProductPage() {
  return (
    <MarketingFrame>
      <section className="px-4 pt-20 pb-16 sm:px-6 sm:pt-28 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <MarketingPageIntro
            eyebrow="Product"
            title="One lead record for preparation, review, and follow-up."
            copy="FlowPilot connects the capabilities already in the product. AI prepares qualification and drafts. People decide what is approved, and sending stays a separate action."
          />
          <div className="mt-14 grid gap-4 lg:grid-cols-2">
            {capabilities.map((item) => {
              const Icon = item.icon;
              return (
                <article
                  key={item.title}
                  className="border-border bg-card rounded-3xl border p-6 sm:p-8"
                >
                  <div className="bg-ai/10 text-ai-text flex size-10 items-center justify-center rounded-xl">
                    <Icon className="size-5" aria-hidden="true" />
                  </div>
                  <h2 className="mt-6 text-xl font-semibold tracking-tight">
                    {item.title}
                  </h2>
                  <p className="text-muted-foreground mt-3 leading-7">{item.copy}</p>
                </article>
              );
            })}
          </div>

          <div className="border-border bg-surface-subtle mt-16 rounded-3xl border p-6 sm:p-8">
            <p className="text-muted-foreground text-xs font-semibold tracking-[0.15em] uppercase">
              Illustrative workspace
            </p>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight">
              How the pieces stay on the same lead
            </h2>
            <ol className="mt-6 grid gap-4 sm:grid-cols-2">
              {[
                "The enquiry stays on the lead.",
                "Qualification and a draft are stored against that lead.",
                "A person reviews the draft before any send.",
                "Activity shows what finished, what failed, and what still needs a person.",
              ].map((step, index) => (
                <li key={step} className="flex gap-3 text-sm leading-6">
                  <span className="bg-foreground text-background flex size-7 shrink-0 items-center justify-center rounded-lg font-mono text-xs">
                    {index + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
            <p className="text-muted-foreground mt-6 text-sm">
              Illustrative summary of the current product. Not a customer deployment.
            </p>
          </div>

          <MarketingRelated
            links={[
              {
                href: "/how-it-works",
                label: "How it works",
                copy: "Follow the sequence from capture through explicit sending and follow-up.",
              },
              {
                href: "/use-cases",
                label: "Use cases",
                copy: "Read example workflows for enquiries, approvals, and follow-ups.",
              },
            ]}
          />
        </div>
      </section>
      <MarketingClosing
        title="Start from a lead your team already needs to answer."
        copy="Create an organization and work through qualification, review, and follow-up with sending kept explicit."
      />
    </MarketingFrame>
  );
}
