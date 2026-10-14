import type { Metadata } from "next";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  Building2,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clock3,
  FileCheck2,
  Inbox,
  LayoutDashboard,
  LockKeyhole,
  MailCheck,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
  Users,
  Workflow,
} from "lucide-react";

import { MarketingFooter } from "@/components/marketing/marketing-footer";
import { MarketingHeader } from "@/components/marketing/marketing-header";
import { buttonVariants } from "@/components/ui/button";
import { marketingPageMetadata } from "@/lib/marketing-metadata";
import { cn } from "@/lib/utils";

export const metadata: Metadata = marketingPageMetadata({
  title: "AI Sales Operations Platform",
  description:
    "Capture leads, qualify enquiries with AI, prepare personalized responses, and coordinate follow-ups with human approval built in.",
  path: "/",
});

const workflowSteps = [
  {
    label: "Enquiry captured",
    detail: "A new lead arrives with the original customer context attached.",
    icon: Inbox,
  },
  {
    label: "Lead qualified",
    detail: "AI structures intent, buying signals, and missing information.",
    icon: Sparkles,
  },
  {
    label: "Response drafted",
    detail: "A personalized reply is prepared from the stored enquiry.",
    icon: MessageSquareText,
  },
  {
    label: "Human reviewed",
    detail: "A person edits, approves, or rejects the draft.",
    icon: FileCheck2,
  },
  {
    label: "Explicitly sent",
    detail: "The approved response is sent only when a user chooses.",
    icon: MailCheck,
  },
  {
    label: "Follow-up tracked",
    detail: "Activity and follow-ups stay visible to the whole team.",
    icon: Activity,
  },
] as const;

const capabilities = [
  {
    eyebrow: "Customer 360",
    title: "Every lead, conversation, and next step in context.",
    copy: "Work from one lead record that brings together contact details, the original enquiry, qualification, response history, human attention, and follow-ups.",
    icon: Users,
    span: "lg:col-span-7",
    visual: (
      <div className="border-border bg-background mt-8 rounded-2xl border p-4 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-semibold">Maya Chen</p>
            <p className="text-muted-foreground text-xs">
              Northstar Studio · New enquiry
            </p>
          </div>
          <span className="bg-success/10 text-success-text rounded-full px-2.5 py-1 text-xs font-medium">
            Qualified
          </span>
        </div>
        <div className="border-border mt-4 grid gap-3 border-t pt-4 sm:grid-cols-2">
          <div>
            <p className="text-muted-foreground text-xs">Intent</p>
            <p className="mt-1 text-sm font-medium">
              Requesting a product demo
            </p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Next action</p>
            <p className="mt-1 text-sm font-medium">Review prepared response</p>
          </div>
        </div>
      </div>
    ),
  },
  {
    eyebrow: "Sales Copilot",
    title: "Ask AI to move one selected lead forward.",
    copy: "Bind a Copilot run to the lead you selected. FlowPilot uses the stored enquiry and keeps the resulting qualification and draft attached to that record.",
    icon: Bot,
    span: "lg:col-span-5",
    visual: (
      <div className="border-ai-border bg-ai/5 mt-8 rounded-2xl border p-4">
        <div className="flex gap-3">
          <span className="bg-ai text-ai-foreground flex size-8 shrink-0 items-center justify-center rounded-lg">
            <Sparkles className="size-4" aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-medium">Stored enquiry selected</p>
            <p className="text-muted-foreground mt-1 text-xs leading-5">
              Qualify this lead and prepare a concise reply for review.
            </p>
          </div>
        </div>
      </div>
    ),
  },
  {
    eyebrow: "Qualification & drafting",
    title: "Turn unstructured enquiries into a clear decision.",
    copy: "Surface intent, qualification signals, confidence, and missing information—then prepare a response that stays grounded in the lead's own enquiry.",
    icon: Sparkles,
    span: "lg:col-span-5",
    visual: (
      <div className="mt-8 space-y-2">
        {[
          ["Buying signal", "Demo requested"],
          ["Missing detail", "Expected timeline"],
          ["Confidence", "High"],
        ].map(([label, value]) => (
          <div
            key={label}
            className="border-border bg-background flex items-center justify-between rounded-xl border px-3 py-2.5"
          >
            <span className="text-muted-foreground text-xs">{label}</span>
            <span className="text-sm font-medium">{value}</span>
          </div>
        ))}
      </div>
    ),
  },
  {
    eyebrow: "Approval Center",
    title: "Keep the human decision exactly where it belongs.",
    copy: "Review the complete draft, edit the wording, approve or reject it, and only then choose whether to send. Approval never sends automatically.",
    icon: FileCheck2,
    span: "lg:col-span-7",
    visual: (
      <div className="border-border bg-background mt-8 rounded-2xl border p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="bg-warning/15 text-warning-text rounded-full px-2.5 py-1 text-xs font-medium">
              Needs review
            </span>
            <span className="text-muted-foreground text-xs">
              Draft · revision 1
            </span>
          </div>
          <div className="flex gap-2">
            <span className="border-border rounded-lg border px-3 py-1.5 text-xs font-medium">
              Edit
            </span>
            <span className="bg-foreground text-background rounded-lg px-3 py-1.5 text-xs font-medium">
              Approve
            </span>
          </div>
        </div>
        <p className="text-muted-foreground mt-4 text-sm leading-6">
          Thanks for getting in touch. We can walk your team through a focused
          product demo next week…
        </p>
      </div>
    ),
  },
  {
    eyebrow: "Follow-up operations",
    title: "Coordinate the work that happens after the first reply.",
    copy: "Schedule and manage follow-ups, see what is overdue, and keep human tasks beside the automated parts of the workflow.",
    icon: Workflow,
    span: "lg:col-span-7",
    visual: (
      <div className="mt-8 grid gap-2 sm:grid-cols-3">
        {[
          ["Today", "Send case study"],
          ["Tomorrow", "Check demo time"],
          ["Friday", "Follow up"],
        ].map(([time, task], index) => (
          <div
            key={task}
            className="border-border bg-background rounded-xl border p-3"
          >
            <p className="text-muted-foreground text-xs">{time}</p>
            <p className="mt-2 text-sm font-medium">{task}</p>
            <div className="mt-3 flex items-center gap-1.5 text-xs">
              <CircleDot
                className={cn(
                  "size-3",
                  index === 0 ? "text-warning-text" : "text-muted-foreground",
                )}
                aria-hidden="true"
              />
              Pending
            </div>
          </div>
        ))}
      </div>
    ),
  },
  {
    eyebrow: "Operational visibility",
    title: "Know what happened and what still needs a person.",
    copy: "Use Command Center queues and organization activity history to find approvals, failed sends, overdue follow-ups, and recent actions.",
    icon: LayoutDashboard,
    span: "lg:col-span-5",
    visual: (
      <div className="mt-8 space-y-3">
        {[
          ["Waiting for review", "2"],
          ["Failed sends", "0"],
          ["Overdue follow-ups", "3"],
        ].map(([label, value]) => (
          <div key={label} className="flex items-center gap-3">
            <div className="bg-muted h-1.5 flex-1 overflow-hidden rounded-full">
              <div
                className="bg-foreground h-full rounded-full"
                style={{
                  width: value === "0" ? "8%" : value === "2" ? "48%" : "70%",
                }}
              />
            </div>
            <span className="w-32 text-xs">{label}</span>
            <span className="w-4 text-right text-sm font-semibold">
              {value}
            </span>
          </div>
        ))}
      </div>
    ),
  },
] as const;

const useCases = [
  {
    icon: BriefcaseBusiness,
    title: "Small B2B sales teams",
    copy: "Give a lean team one shared process for handling inbound interest.",
  },
  {
    icon: Building2,
    title: "Service businesses",
    copy: "Bring consistency to enquiries that need thoughtful, personalized replies.",
  },
  {
    icon: Clock3,
    title: "Follow-up focused teams",
    copy: "Keep responses and next actions from disappearing across separate tools.",
  },
  {
    icon: ShieldCheck,
    title: "Human-led AI adoption",
    copy: "Use AI for preparation while people retain control of customer communication.",
  },
] as const;

function SectionIntro({
  eyebrow,
  title,
  copy,
  centered = false,
}: {
  eyebrow: string;
  title: string;
  copy: string;
  centered?: boolean;
}) {
  return (
    <div className={cn("max-w-3xl", centered && "mx-auto text-center")}>
      <p className="text-ai-text text-xs font-semibold tracking-[0.18em] uppercase">
        {eyebrow}
      </p>
      <h2 className="mt-4 text-3xl leading-tight font-semibold tracking-[-0.035em] text-balance sm:text-4xl lg:text-5xl">
        {title}
      </h2>
      <p className="text-muted-foreground mt-5 text-base leading-7 text-pretty sm:text-lg sm:leading-8">
        {copy}
      </p>
    </div>
  );
}

function ProductWindow() {
  return (
    <div
      className="border-border bg-card relative overflow-hidden rounded-2xl border shadow-[0_30px_80px_-35px_oklch(0.2_0.01_265/35%)]"
      aria-label="Illustrative FlowPilot Approval Center product view"
    >
      <div className="border-border bg-surface-subtle flex h-11 items-center gap-2 border-b px-4">
        <span className="size-2.5 rounded-full bg-red-400/70" />
        <span className="size-2.5 rounded-full bg-amber-400/70" />
        <span className="size-2.5 rounded-full bg-emerald-400/70" />
        <span className="text-muted-foreground ml-2 text-[0.68rem] font-medium">
          FlowPilot workspace
        </span>
      </div>
      <div className="grid min-h-[30rem] sm:grid-cols-[11rem_minmax(0,1fr)]">
        <aside className="border-border bg-surface-subtle hidden border-r p-3 sm:block">
          <div className="mb-5 flex items-center gap-2 px-2 py-1">
            <span className="bg-foreground text-background flex size-7 items-center justify-center rounded-md text-xs font-semibold">
              N
            </span>
            <div>
              <p className="text-xs font-semibold">Northstar</p>
              <p className="text-muted-foreground text-[0.62rem]">FlowPilot</p>
            </div>
          </div>
          {[
            [LayoutDashboard, "Command Center"],
            [Users, "Leads"],
            [Inbox, "AI Inbox"],
            [FileCheck2, "Approvals"],
            [Bot, "AI Agents"],
            [Activity, "Activity"],
          ].map(([Icon, label]) => (
            <div
              key={label as string}
              className={cn(
                "mb-1 flex items-center gap-2 rounded-md px-2 py-1.5 text-[0.68rem]",
                label === "Approvals"
                  ? "bg-foreground text-background font-medium"
                  : "text-muted-foreground",
              )}
            >
              <Icon className="size-3.5" aria-hidden="true" />
              {label as string}
            </div>
          ))}
        </aside>
        <div className="p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-lg font-semibold tracking-tight">
                Approval Center
              </p>
              <p className="text-muted-foreground mt-1 text-xs">
                Review AI-prepared responses before anything is sent.
              </p>
            </div>
            <span className="border-border bg-background rounded-lg border px-2.5 py-1 text-[0.68rem] font-medium">
              2 need review
            </span>
          </div>

          <div className="mt-5 grid gap-3 lg:grid-cols-[0.8fr_1.2fr]">
            <div className="space-y-2">
              <div className="border-ai-border bg-ai/5 rounded-xl border p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold">Maya Chen</p>
                  <span className="text-warning-text text-[0.62rem] font-medium">
                    NEEDS REVIEW
                  </span>
                </div>
                <p className="text-muted-foreground mt-1 text-[0.68rem]">
                  Northstar Studio
                </p>
                <p className="mt-3 line-clamp-2 text-[0.7rem] leading-5">
                  Interested in automating inbound qualification and scheduling
                  a demo.
                </p>
              </div>
              <div className="border-border rounded-xl border p-3 opacity-70">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold">Jon Bell</p>
                  <span className="text-warning-text text-[0.62rem] font-medium">
                    NEEDS REVIEW
                  </span>
                </div>
                <p className="text-muted-foreground mt-1 text-[0.68rem]">
                  Tandem Services
                </p>
              </div>
            </div>

            <div className="border-border rounded-xl border p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">Prepared response</p>
                  <p className="text-muted-foreground mt-1 text-[0.68rem]">
                    Grounded in Maya&apos;s stored enquiry
                  </p>
                </div>
                <span className="bg-ai/10 text-ai-text rounded-full px-2 py-1 text-[0.62rem] font-semibold">
                  AI DRAFT
                </span>
              </div>
              <div className="bg-surface-subtle mt-4 rounded-lg p-3 text-[0.7rem] leading-5">
                Hi Maya,
                <br />
                <br />
                Thanks for sharing how Northstar handles inbound enquiries. We
                can show you how FlowPilot qualifies each enquiry, prepares a
                response, and keeps your team in control before sending.
              </div>
              <div className="border-border mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-4">
                <p className="text-muted-foreground max-w-[12rem] text-[0.62rem] leading-4">
                  Approval does not send the email.
                </p>
                <div className="flex gap-2">
                  <span className="border-border rounded-md border px-2.5 py-1 text-[0.68rem] font-medium">
                    Edit
                  </span>
                  <span className="bg-foreground text-background rounded-md px-2.5 py-1 text-[0.68rem] font-medium">
                    Approve
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="border-border mt-4 flex items-center gap-2 border-t pt-4">
            <CheckCircle2
              className="text-success-text size-4"
              aria-hidden="true"
            />
            <p className="text-muted-foreground text-[0.68rem]">
              Qualification complete · Draft prepared · Human decision pending
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function MarketingHomePage() {
  return (
    <>
      <a
        href="#main-content"
        className="bg-background focus:ring-ring fixed top-3 left-3 z-[60] -translate-y-20 rounded-lg px-4 py-2 text-sm font-medium shadow-lg focus:translate-y-0 focus:ring-2"
      >
        Skip to content
      </a>
      <MarketingHeader />

      <main id="main-content">
        <section className="relative overflow-hidden">
          <div
            className="pointer-events-none absolute inset-0 -z-10 opacity-70 dark:opacity-35"
            aria-hidden="true"
          >
            <div className="bg-ai/15 absolute -top-40 left-1/2 h-[34rem] w-[54rem] -translate-x-1/2 rounded-full blur-3xl" />
            <div className="absolute inset-0 bg-[linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] [mask-image:linear-gradient(to_bottom,black,transparent_72%)] bg-[size:48px_48px]" />
          </div>
          <div className="mx-auto grid max-w-7xl gap-14 px-4 pt-20 pb-20 sm:px-6 sm:pt-28 lg:grid-cols-[0.85fr_1.15fr] lg:items-center lg:gap-16 lg:px-8 lg:pt-32 lg:pb-28">
            <div className="max-w-2xl">
              <div className="border-ai-border bg-ai/5 text-ai-text inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold">
                <Sparkles className="size-3.5" aria-hidden="true" />
                AI sales operations, with people in control
              </div>
              <h1 className="mt-7 text-5xl leading-[0.98] font-semibold tracking-[-0.055em] text-balance sm:text-6xl xl:text-[4.25rem]">
                Turn new enquiries into your next customers.
              </h1>
              <p className="text-muted-foreground mt-7 max-w-xl text-lg leading-8 text-pretty">
                Capture leads, qualify enquiries with AI, prepare personalized
                responses, and coordinate follow-ups in one workspace. Your team
                stays in control of every important action.
              </p>
              <div className="mt-9 flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/register"
                  className={buttonVariants({
                    size: "lg",
                    className: "h-11 px-5 text-base",
                  })}
                >
                  Get started
                  <ArrowRight aria-hidden="true" />
                </Link>
                <Link
                  href="/product"
                  className={buttonVariants({
                    variant: "outline",
                    size: "lg",
                    className: "h-11 px-5 text-base",
                  })}
                >
                  Explore the product
                  <ChevronRight aria-hidden="true" />
                </Link>
              </div>
              <div className="text-muted-foreground mt-7 flex flex-wrap gap-x-5 gap-y-2 text-xs">
                {[
                  "Human approval",
                  "Explicit sending",
                  "Organization-scoped data",
                ].map((item) => (
                  <span key={item} className="flex items-center gap-1.5">
                    <Check
                      className="text-success-text size-3.5"
                      aria-hidden="true"
                    />
                    {item}
                  </span>
                ))}
              </div>
            </div>

            <div className="relative lg:-mr-24">
              <div className="border-ai-border bg-ai/5 absolute -inset-5 -z-10 rounded-[2rem] border blur-sm" />
              <ProductWindow />
              <p className="text-muted-foreground mt-3 text-center text-xs">
                Illustrative product walkthrough using representative workspace
                data.
              </p>
            </div>
          </div>
        </section>

        <section className="border-border bg-surface-subtle/70 border-y">
          <div className="mx-auto grid max-w-7xl gap-8 px-4 py-8 sm:grid-cols-3 sm:px-6 lg:px-8">
            {[
              [
                "One connected workflow",
                "Lead context stays with qualification, drafting, approval, and follow-up.",
              ],
              [
                "AI prepares the work",
                "Your team reviews the decision and customer-facing response.",
              ],
              [
                "Sending stays explicit",
                "An approved response is sent only when a user chooses to send it.",
              ],
            ].map(([title, copy]) => (
              <div key={title} className="flex gap-3">
                <CheckCircle2
                  className="text-ai-text mt-0.5 size-5 shrink-0"
                  aria-hidden="true"
                />
                <div>
                  <p className="font-medium">{title}</p>
                  <p className="text-muted-foreground mt-1 text-sm leading-6">
                    {copy}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section
          id="product"
          className="scroll-mt-20 px-4 py-24 sm:px-6 sm:py-32 lg:px-8"
        >
          <div className="mx-auto max-w-7xl">
            <SectionIntro
              eyebrow="The complete lead journey"
              title="See the work move forward, without losing control."
              copy="FlowPilot connects the steps that normally live across forms, spreadsheets, AI chats, inboxes, and task lists. The demonstration below reflects capabilities available in the product today."
              centered
            />

            <div className="mt-14 grid gap-3 md:grid-cols-2 lg:grid-cols-6">
              {workflowSteps.map((step, index) => {
                const Icon = step.icon;
                return (
                  <article
                    key={step.label}
                    className="border-border bg-card relative rounded-2xl border p-4 shadow-sm lg:col-span-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="bg-foreground text-background flex size-8 items-center justify-center rounded-lg">
                        <Icon className="size-4" aria-hidden="true" />
                      </span>
                      <span className="text-muted-foreground font-mono text-xs">
                        0{index + 1}
                      </span>
                    </div>
                    <h3 className="mt-5 text-sm font-semibold">{step.label}</h3>
                    <p className="text-muted-foreground mt-2 text-xs leading-5">
                      {step.detail}
                    </p>
                    {index < workflowSteps.length - 1 ? (
                      <ChevronRight
                        className="text-border-strong absolute top-1/2 -right-3 z-10 hidden size-5 -translate-y-1/2 lg:block"
                        aria-hidden="true"
                      />
                    ) : null}
                  </article>
                );
              })}
            </div>

            <div className="mt-16">
              <ProductWindow />
            </div>
          </div>
        </section>

        <section className="bg-surface-subtle border-border border-y px-4 py-24 sm:px-6 sm:py-32 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <SectionIntro
              eyebrow="Product capabilities"
              title="Built around the work your sales team actually does."
              copy="Each workspace has a clear purpose, while the lead record and activity history keep the full story connected."
            />
            <div className="mt-14 grid gap-4 lg:grid-cols-12">
              {capabilities.map((capability) => {
                const Icon = capability.icon;
                return (
                  <article
                    key={capability.title}
                    className={cn(
                      "border-border bg-card overflow-hidden rounded-3xl border p-6 shadow-sm sm:p-8",
                      capability.span,
                    )}
                  >
                    <div className="bg-ai/10 text-ai-text flex size-10 items-center justify-center rounded-xl">
                      <Icon className="size-5" aria-hidden="true" />
                    </div>
                    <p className="text-ai-text mt-6 text-xs font-semibold tracking-[0.15em] uppercase">
                      {capability.eyebrow}
                    </p>
                    <h3 className="mt-3 max-w-xl text-2xl leading-tight font-semibold tracking-[-0.025em]">
                      {capability.title}
                    </h3>
                    <p className="text-muted-foreground mt-4 max-w-2xl leading-7">
                      {capability.copy}
                    </p>
                    {capability.visual}
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section
          id="how-it-works"
          className="scroll-mt-20 px-4 py-24 sm:px-6 sm:py-32 lg:px-8"
        >
          <div className="mx-auto grid max-w-7xl gap-14 lg:grid-cols-[0.8fr_1.2fr] lg:items-start lg:gap-24">
            <div className="lg:sticky lg:top-28">
              <SectionIntro
                eyebrow="How it works"
                title="AI moves quickly. Your controls stay clear."
                copy="FlowPilot separates preparation, approval, and sending so your team always knows what the system has done—and what still needs a person."
              />
              <div className="mt-8 flex flex-col items-start gap-3">
                <Link
                  href="/how-it-works"
                  className="text-sm font-medium underline underline-offset-4"
                >
                  Read the full sequence
                </Link>
                <Link
                  href="/register"
                  className={buttonVariants({
                    size: "lg",
                    className: "px-4",
                  })}
                >
                  Start with your organization
                  <ArrowRight aria-hidden="true" />
                </Link>
              </div>
            </div>
            <ol className="before:bg-border relative grid gap-5 before:absolute before:top-7 before:bottom-7 before:left-7 before:w-px">
              {[
                {
                  number: "01",
                  title: "Capture or create the lead",
                  copy: "Start from a hosted enquiry form or create the lead directly. FlowPilot keeps the original enquiry on the customer record.",
                },
                {
                  number: "02",
                  title: "Qualify and prepare",
                  copy: "Run qualification and response drafting from Customer 360, a Sales Agent run, or the lead-bound Sales Copilot.",
                },
                {
                  number: "03",
                  title: "Review and approve",
                  copy: "A person reads the draft, edits it if needed, and makes an explicit approval or rejection decision.",
                },
                {
                  number: "04",
                  title: "Send, track, and follow up",
                  copy: "Approval does not send. A user separately sends the approved response, then tracks activity and follow-up work.",
                },
              ].map((step) => (
                <li
                  key={step.number}
                  className="border-border bg-card relative grid grid-cols-[3.5rem_1fr] gap-4 rounded-2xl border p-5 shadow-sm sm:p-6"
                >
                  <span className="bg-foreground text-background relative z-10 flex size-10 items-center justify-center rounded-xl font-mono text-xs font-semibold">
                    {step.number}
                  </span>
                  <div>
                    <h3 className="text-lg font-semibold">{step.title}</h3>
                    <p className="text-muted-foreground mt-2 leading-7">
                      {step.copy}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="bg-foreground text-background overflow-hidden px-4 py-24 sm:px-6 sm:py-32 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <div className="max-w-3xl">
              <p className="text-background/60 text-xs font-semibold tracking-[0.18em] uppercase">
                Why FlowPilot
              </p>
              <h2 className="mt-4 text-3xl leading-tight font-semibold tracking-[-0.035em] text-balance sm:text-4xl lg:text-5xl">
                Replace the handoffs, not the human judgment.
              </h2>
              <p className="text-background/65 mt-5 text-lg leading-8">
                FlowPilot is designed for teams that want one controlled sales
                workflow—not another disconnected place to copy, paste, and
                remember the next step.
              </p>
            </div>
            <div className="bg-background/15 mt-14 grid gap-px overflow-hidden rounded-2xl lg:grid-cols-3">
              {[
                {
                  label: "Disconnected tools",
                  title:
                    "Context gets copied between forms, sheets, inboxes, and AI chats.",
                  copy: "The team has to reconstruct why a response was written and what should happen next.",
                },
                {
                  label: "Conventional workflow",
                  title:
                    "Records are organized, but preparation and follow-up remain manual.",
                  copy: "Customer context exists, yet the work still depends on repeated handoffs.",
                },
                {
                  label: "FlowPilot",
                  title:
                    "Lead context, AI preparation, approval, and follow-up stay connected.",
                  copy: "People retain the final decision while the system keeps the operational trail together.",
                  highlighted: true,
                },
              ].map((item) => (
                <article
                  key={item.label}
                  className={cn(
                    "min-h-72 p-7 sm:p-8",
                    item.highlighted
                      ? "bg-background text-foreground"
                      : "bg-foreground",
                  )}
                >
                  <p
                    className={cn(
                      "text-xs font-semibold tracking-[0.15em] uppercase",
                      item.highlighted ? "text-ai-text" : "text-background/50",
                    )}
                  >
                    {item.label}
                  </p>
                  <h3 className="mt-6 text-xl leading-8 font-semibold">
                    {item.title}
                  </h3>
                  <p
                    className={cn(
                      "mt-5 leading-7",
                      item.highlighted
                        ? "text-muted-foreground"
                        : "text-background/60",
                    )}
                  >
                    {item.copy}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="px-4 py-24 sm:px-6 sm:py-32 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <SectionIntro
              eyebrow="Designed for"
              title="A focused workspace for teams growing through inbound demand."
              copy="These are intended use cases for FlowPilot—not claims about existing customers."
              centered
            />
            <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {useCases.map((useCase) => {
                const Icon = useCase.icon;
                return (
                  <article
                    key={useCase.title}
                    className="border-border bg-card rounded-2xl border p-6 shadow-sm"
                  >
                    <Icon className="text-ai-text size-6" aria-hidden="true" />
                    <h3 className="mt-8 text-lg font-semibold">
                      {useCase.title}
                    </h3>
                    <p className="text-muted-foreground mt-3 leading-7">
                      {useCase.copy}
                    </p>
                  </article>
                );
              })}
            </div>
            <p className="mt-8 text-center">
              <Link
                href="/use-cases"
                className="text-sm font-medium underline underline-offset-4"
              >
                See example workflows
              </Link>
            </p>
          </div>
        </section>

        <section
          id="pricing"
          className="bg-surface-subtle border-border scroll-mt-20 border-y px-4 py-24 sm:px-6 sm:py-32 lg:px-8"
        >
          <div className="mx-auto max-w-7xl">
            <SectionIntro
              eyebrow="Pricing preview"
              title="Start exploring today. Commercial plans are still being shaped."
              copy="FlowPilot does not currently include in-product billing, subscription management, usage metering, or enforced trial limits. The packaging below describes the intended direction and is not a published price list."
              centered
            />
            <div className="mt-14 grid gap-4 lg:grid-cols-3">
              {[
                {
                  label: "Available today",
                  title: "Create an organization",
                  copy: "Register an owner account and explore the implemented sales workspace.",
                  points: [
                    "Organization workspace",
                    "Lead and enquiry workflow",
                    "Human approval controls",
                  ],
                  action: true,
                },
                {
                  label: "Planned packaging",
                  title: "Team plans",
                  copy: "Future self-serve plans are expected to support growing teams and usage needs.",
                  points: [
                    "Pricing not yet published",
                    "Limits not yet implemented",
                    "Billing not yet connected",
                  ],
                },
                {
                  label: "Future option",
                  title: "Larger organizations",
                  copy: "Business packaging may evolve for organizations with broader operational requirements.",
                  points: [
                    "Scope to be validated",
                    "No enterprise claims today",
                    "No contact-sales workflow yet",
                  ],
                },
              ].map((plan) => (
                <article
                  key={plan.title}
                  className={cn(
                    "border-border rounded-3xl border p-7 sm:p-8",
                    plan.action ? "bg-card shadow-lg" : "bg-background/60",
                  )}
                >
                  <p className="text-ai-text text-xs font-semibold tracking-[0.15em] uppercase">
                    {plan.label}
                  </p>
                  <h3 className="mt-4 text-2xl font-semibold tracking-tight">
                    {plan.title}
                  </h3>
                  <p className="text-muted-foreground mt-4 min-h-20 leading-7">
                    {plan.copy}
                  </p>
                  <ul className="mt-7 grid gap-3">
                    {plan.points.map((point) => (
                      <li key={point} className="flex gap-2.5 text-sm">
                        <Check
                          className="text-success-text mt-0.5 size-4 shrink-0"
                          aria-hidden="true"
                        />
                        {point}
                      </li>
                    ))}
                  </ul>
                  {plan.action ? (
                    <Link
                      href="/register"
                      className={buttonVariants({
                        size: "lg",
                        className: "mt-8 w-full",
                      })}
                    >
                      Get started
                      <ArrowRight aria-hidden="true" />
                    </Link>
                  ) : (
                    <p className="border-border text-muted-foreground mt-8 border-t pt-5 text-xs">
                      Details will be published only after commercial
                      validation.
                    </p>
                  )}
                </article>
              ))}
            </div>
          </div>
        </section>

        <section
          id="trust"
          className="scroll-mt-20 px-4 py-24 sm:px-6 sm:py-32 lg:px-8"
        >
          <div className="mx-auto grid max-w-7xl gap-14 lg:grid-cols-[0.8fr_1.2fr] lg:items-center lg:gap-24">
            <SectionIntro
              eyebrow="Trust by design"
              title="Controls that match the responsibility of customer communication."
              copy="FlowPilot's current application is built around organization boundaries, role-aware operations, human review, explicit sending, and a durable activity history."
            />
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                {
                  icon: LockKeyhole,
                  title: "Organization isolation",
                  copy: "Repository and service queries scope customer records to the authenticated organization.",
                },
                {
                  icon: Users,
                  title: "Role-aware controls",
                  copy: "Membership roles protect administrative agent configuration and organization operations.",
                },
                {
                  icon: FileCheck2,
                  title: "Human approval",
                  copy: "Drafts remain reviewable and editable before an approval decision.",
                },
                {
                  icon: MailCheck,
                  title: "Explicit sending",
                  copy: "Approval and email sending are separate user actions.",
                },
                {
                  icon: Activity,
                  title: "Activity history",
                  copy: "AI, approval, human, and system events are recorded for operational visibility.",
                },
                {
                  icon: ShieldCheck,
                  title: "No invented certifications",
                  copy: "Compliance certifications and uptime guarantees are not claimed here.",
                },
              ].map((item) => {
                const Icon = item.icon;
                return (
                  <article
                    key={item.title}
                    className="border-border rounded-2xl border p-5"
                  >
                    <Icon className="text-ai-text size-5" aria-hidden="true" />
                    <h3 className="mt-5 font-semibold">{item.title}</h3>
                    <p className="text-muted-foreground mt-2 text-sm leading-6">
                      {item.copy}
                    </p>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section className="px-4 pb-8 sm:px-6 sm:pb-12 lg:px-8">
          <div className="bg-foreground text-background relative mx-auto max-w-7xl overflow-hidden rounded-[2rem] px-6 py-16 text-center sm:px-12 sm:py-20">
            <div
              className="bg-ai/25 absolute top-0 left-1/2 h-64 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl"
              aria-hidden="true"
            />
            <div className="relative mx-auto max-w-3xl">
              <p className="text-background/60 text-xs font-semibold tracking-[0.18em] uppercase">
                Bring the workflow together
              </p>
              <h2 className="mt-5 text-3xl leading-tight font-semibold tracking-[-0.04em] text-balance sm:text-5xl">
                Give every new enquiry a clear next step.
              </h2>
              <p className="text-background/65 mx-auto mt-5 max-w-2xl text-base leading-7 sm:text-lg">
                Create your FlowPilot organization and explore a sales workflow
                where AI prepares the work and your team stays in control.
              </p>
              <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
                <Link
                  href="/register"
                  className="bg-background text-foreground hover:bg-background/90 inline-flex h-11 items-center justify-center gap-2 rounded-lg px-5 text-base font-medium transition-colors"
                >
                  Get started
                  <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
                <Link
                  href="/login"
                  className="border-background/20 hover:bg-background/10 inline-flex h-11 items-center justify-center rounded-lg border px-5 text-base font-medium transition-colors"
                >
                  Sign in
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </>
  );
}
