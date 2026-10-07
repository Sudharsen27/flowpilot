"use client";

import type { ReactNode } from "react";

import { BrandLockup } from "@/components/brand-lockup";
import { ThemeToggle } from "@/components/layout/theme-toggle";

const steps = ["Qualify", "Draft", "Approve"] as const;

type AuthFrameProps = {
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
};

export function AuthFrame({ title, description, children, footer }: AuthFrameProps) {
  return (
    <div className="grid min-h-svh lg:grid-cols-[minmax(0,1.15fr)_minmax(24rem,34rem)]">
      <aside className="relative hidden overflow-hidden border-r border-white/10 bg-[oklch(0.94_0.03_155)] lg:flex lg:flex-col dark:border-white/8 dark:bg-[oklch(0.2_0.04_165)]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-28 -left-16 size-80 rounded-full bg-[oklch(0.72_0.12_160/0.45)] blur-3xl dark:bg-[oklch(0.55_0.1_165/0.35)]"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute right-0 bottom-0 size-72 rounded-full bg-[oklch(0.85_0.06_90/0.7)] blur-3xl dark:bg-[oklch(0.35_0.05_170/0.4)]"
        />

        <div className="relative flex flex-1 flex-col justify-center px-10 py-10 xl:px-14">
          <BrandLockup />

          <p className="text-ai-text mt-10 text-xs font-medium tracking-wide uppercase">
            For teams selling today
          </p>
          <h2 className="mt-3 max-w-lg text-4xl leading-tight font-semibold tracking-tight text-balance">
            New enquiries become replies your team can send.
          </h2>
          <ol className="mt-5 flex flex-wrap gap-2" aria-label="How FlowPilot works">
            {steps.map((step, index) => (
              <li
                key={step}
                className="border-border/80 bg-card/80 flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm shadow-card backdrop-blur-sm"
              >
                <span className="text-ai-text font-mono text-[0.6875rem]">
                  {String(index + 1).padStart(2, "0")}
                </span>
                {step}
              </li>
            ))}
          </ol>

          <article className="border-border bg-card/90 shadow-overlay mt-8 max-w-md rounded-2xl border p-4 backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3">
              <p className="text-muted-foreground text-[0.6875rem] font-medium tracking-wide uppercase">
                Example
              </p>
              <span className="bg-warning/15 text-warning-text rounded-full px-2 py-0.5 text-[0.6875rem] font-medium">
                Waiting for review
              </span>
            </div>
            <p className="mt-3 text-sm font-medium">Website enquiry</p>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              “Can you share pricing for a 40-person team?”
            </p>
            <div className="border-ai-border bg-ai/8 mt-3 rounded-xl border px-3 py-3">
              <p className="text-ai-text text-[0.6875rem] font-medium tracking-wide uppercase">
                Agent draft
              </p>
              <p className="mt-1 text-sm leading-6">
                Thanks for writing in. I can send pricing for a 40-person team and a time to talk this week.
              </p>
            </div>
            <p className="text-muted-foreground mt-3 text-xs leading-5">
              Example. A person approves the send.
            </p>
          </article>
        </div>
      </aside>

      <div className="bg-background relative flex min-h-svh flex-col">
        <div className="flex items-center justify-between px-6 py-4">
          <BrandLockup size="sm" className="lg:hidden" />
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>
        <main className="flex flex-1 flex-col justify-center px-6 pb-12">
          <div className="mx-auto w-full max-w-sm">
            <p className="text-ai-text text-xs font-medium tracking-wide uppercase lg:hidden">
              New enquiries become approved replies
            </p>
            <h1 className="text-page-title mt-3 font-semibold tracking-tight lg:mt-0">
              {title}
            </h1>
            <p className="text-muted-foreground mt-2 text-sm leading-6">{description}</p>
            <div className="border-border bg-card shadow-card mt-8 rounded-2xl border p-5">
              {children}
            </div>
            <div className="text-muted-foreground mt-5 text-sm">{footer}</div>
          </div>
        </main>
      </div>
    </div>
  );
}
