import type { Metadata } from "next";

import { ContactForm } from "@/components/marketing/contact-form";
import {
  MarketingFrame,
  MarketingPageIntro,
  MarketingRelated,
} from "@/components/marketing/marketing-frame";
import { marketingPageMetadata } from "@/lib/marketing-metadata";

export const metadata: Metadata = marketingPageMetadata({
  title: "Contact",
  description:
    "Request a FlowPilot demo or contact the team. A person reviews the message. Submitting this form does not create an account or send customer email.",
  path: "/contact",
});

export default function ContactPage() {
  return (
    <MarketingFrame>
      <section className="px-4 py-16 sm:px-6 sm:py-24 lg:px-8">
        <div className="mx-auto max-w-3xl">
          <MarketingPageIntro
            eyebrow="Contact"
            title="Request a demo or contact the team."
            copy="Send a short note about the workflow you want to see. FlowPilot emails the team, then sends you a short acknowledgement when delivery accepts it. A person replies separately. This form does not create an organization, book a calendar slot, or send email to your customers."
          />
          <div className="mt-10">
            <ContactForm />
          </div>
          <MarketingRelated
            links={[
              {
                href: "/product",
                label: "Product",
                copy: "Review lead context, qualification, approval, and explicit sending.",
              },
              {
                href: "/how-it-works",
                label: "How it works",
                copy: "See the sequence from a lead through review and follow-up.",
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
    </MarketingFrame>
  );
}
