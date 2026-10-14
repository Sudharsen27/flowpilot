import type { Metadata } from "next";

import {
  MarketingClosing,
  MarketingFrame,
  MarketingPageIntro,
  MarketingRelated,
} from "@/components/marketing/marketing-frame";
import { marketingPageMetadata } from "@/lib/marketing-metadata";

export const metadata: Metadata = marketingPageMetadata({
  title: "Use cases",
  description:
    "Example sales workflows in FlowPilot: new enquiries, consistent response drafts, human approval, follow-ups, and agent execution outcomes.",
  path: "/use-cases",
});

const examples = [
  {
    title: "Handling a new enquiry",
    copy: "Example: a studio asks for a demo on the hosted form. FlowPilot stores a new lead with that enquiry. Someone opens the lead, reads the original message, and starts qualification when they are ready. The form itself does not send a reply.",
  },
  {
    title: "Preparing a consistent response",
    copy: "Example: two teammates need the same facts from the enquiry in the reply. A draft is generated from that stored text so the team edits one response instead of rewriting it in a separate inbox.",
  },
  {
    title: "Keeping a person in the approval loop",
    copy: "Example: the draft mentions a meeting time the enquiry never confirmed. A reviewer edits that sentence, then approves the revised text. The email is still unsent until someone uses the send action.",
  },
  {
    title: "Tracking follow-ups and overdue work",
    copy: "Example: after a reply is sent, the team schedules a reminder. If it stays open past the due time, it appears as overdue. Completing or cancelling the follow-up is still a human decision unless an enabled email follow-up worker sends a due email follow-up.",
  },
  {
    title: "Understanding agent execution outcomes",
    copy: "Example: a lead-bound Copilot run finishes or fails. The lead timeline can show that completion or failure. A skipped or failed Sales Agent auto-start is shown as that outcome, not as a draft waiting for approval.",
  },
] as const;

export default function UseCasesPage() {
  return (
    <MarketingFrame>
      <section className="px-4 pt-20 pb-16 sm:px-6 sm:pt-28 lg:px-8">
        <div className="mx-auto max-w-7xl">
          <MarketingPageIntro
            eyebrow="Use cases"
            title="Example workflows for inbound sales work."
            copy="These are practical situations the current product can support. They are examples, not customer case studies, and they do not describe measured results."
          />
          <div className="mt-14 grid gap-4">
            {examples.map((example) => (
              <article
                key={example.title}
                className="border-border bg-card rounded-3xl border p-6 sm:p-8"
              >
                <p className="text-ai-text text-xs font-semibold tracking-[0.15em] uppercase">
                  Example
                </p>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight">
                  {example.title}
                </h2>
                <p className="text-muted-foreground mt-4 max-w-3xl leading-7">
                  {example.copy}
                </p>
              </article>
            ))}
          </div>
          <MarketingRelated
            links={[
              {
                href: "/product",
                label: "Product",
                copy: "Review the capabilities behind these examples.",
              },
              {
                href: "/how-it-works",
                label: "How it works",
                copy: "See the order of capture, review, approval, and sending.",
              },
            ]}
          />
        </div>
      </section>
      <MarketingClosing
        title="Try the workflow with your own organization."
        copy="Registration creates a workspace. It does not publish a price, book a demo, or send customer email."
      />
    </MarketingFrame>
  );
}
