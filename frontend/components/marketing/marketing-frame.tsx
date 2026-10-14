import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { MarketingFooter } from "@/components/marketing/marketing-footer";
import { MarketingHeader } from "@/components/marketing/marketing-header";
import { cn } from "@/lib/utils";

export function MarketingFrame({ children }: { children: ReactNode }) {
  return (
    <>
      <a
        href="#main-content"
        className="bg-background focus:ring-ring fixed top-3 left-3 z-[60] -translate-y-20 rounded-lg px-4 py-2 text-sm font-medium shadow-lg focus:translate-y-0 focus:ring-2"
      >
        Skip to content
      </a>
      <MarketingHeader />
      <main id="main-content">{children}</main>
      <MarketingFooter />
    </>
  );
}

export function MarketingPageIntro({
  eyebrow,
  title,
  copy,
}: {
  eyebrow: string;
  title: string;
  copy: string;
}) {
  return (
    <div className="max-w-3xl">
      <p className="text-ai-text text-xs font-semibold tracking-[0.18em] uppercase">
        {eyebrow}
      </p>
      <h1 className="mt-5 text-4xl leading-[1.05] font-semibold tracking-[-0.045em] text-balance sm:text-5xl">
        {title}
      </h1>
      <p className="text-muted-foreground mt-6 text-lg leading-8 text-pretty">
        {copy}
      </p>
    </div>
  );
}

export function MarketingClosing({
  title,
  copy,
}: {
  title: string;
  copy: string;
}) {
  return (
    <section className="px-4 pb-8 sm:px-6 sm:pb-12 lg:px-8">
      <div className="bg-foreground text-background relative mx-auto max-w-7xl overflow-hidden rounded-[2rem] px-6 py-16 text-center sm:px-12 sm:py-20">
        <h2 className="mx-auto max-w-3xl text-3xl leading-tight font-semibold tracking-[-0.04em] text-balance sm:text-4xl">
          {title}
        </h2>
        <p className="text-background/65 mx-auto mt-5 max-w-2xl text-base leading-7">
          {copy}
        </p>
        <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
          <Link
            href="/register"
            className="bg-background text-foreground hover:bg-background/90 focus-visible:ring-background inline-flex h-11 items-center justify-center gap-2 rounded-lg px-5 text-base font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none"
          >
            Get started
            <ArrowRight aria-hidden="true" className="size-4" />
          </Link>
          <Link
            href="/login"
            className="border-background/20 hover:bg-background/10 focus-visible:ring-background inline-flex h-11 items-center justify-center rounded-lg border px-5 text-base font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none"
          >
            Sign in
          </Link>
        </div>
      </div>
    </section>
  );
}

export function MarketingRelated({
  links,
}: {
  links: readonly { href: string; label: string; copy: string }[];
}) {
  return (
    <nav aria-label="Related pages" className="mt-16 grid gap-3 sm:grid-cols-2">
      {links.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={cn(
            "border-border hover:bg-muted focus-visible:ring-ring rounded-2xl border p-5 transition-colors focus-visible:ring-2 focus-visible:outline-none",
          )}
        >
          <p className="font-semibold">{link.label}</p>
          <p className="text-muted-foreground mt-2 text-sm leading-6">{link.copy}</p>
        </Link>
      ))}
    </nav>
  );
}
