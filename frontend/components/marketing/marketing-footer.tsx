import Link from "next/link";

import { BrandLockup } from "@/components/brand-lockup";

const productLinks = [
  ["Product", "/product"],
  ["How it works", "/how-it-works"],
  ["Use cases", "/use-cases"],
  ["Contact", "/contact"],
  ["Pricing preview", "/#pricing"],
  ["Trust", "/#trust"],
] as const;

export function MarketingFooter() {
  return (
    <footer className="border-border border-t">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_0.6fr_0.6fr] lg:px-8">
        <div>
          <BrandLockup />
          <p className="text-muted-foreground mt-5 max-w-sm text-sm leading-6">
            AI sales operations for teams that want faster preparation,
            connected follow-up, and human control over customer communication.
          </p>
        </div>
        <div>
          <p className="text-sm font-semibold">Product</p>
          <nav aria-label="Footer product" className="mt-4 grid gap-3">
            {productLinks.map(([label, href]) => (
              <Link
                key={href}
                href={href}
                className="text-muted-foreground hover:text-foreground focus-visible:ring-ring rounded-sm text-sm focus-visible:ring-2 focus-visible:outline-none"
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
        <div>
          <p className="text-sm font-semibold">Access</p>
          <nav aria-label="Footer access" className="mt-4 grid gap-3">
            <Link
              href="/register"
              className="text-muted-foreground hover:text-foreground focus-visible:ring-ring rounded-sm text-sm focus-visible:ring-2 focus-visible:outline-none"
            >
              Get started
            </Link>
            <Link
              href="/login"
              className="text-muted-foreground hover:text-foreground focus-visible:ring-ring rounded-sm text-sm focus-visible:ring-2 focus-visible:outline-none"
            >
              Sign in
            </Link>
            <Link
              href="/dashboard"
              className="text-muted-foreground hover:text-foreground focus-visible:ring-ring rounded-sm text-sm focus-visible:ring-2 focus-visible:outline-none"
            >
              Command Center
            </Link>
          </nav>
        </div>
      </div>
      <div className="border-border border-t">
        <div className="text-muted-foreground mx-auto flex max-w-7xl flex-col gap-2 px-4 py-5 text-xs sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <p>© {new Date().getFullYear()} FlowPilot.</p>
          <p>Product capabilities shown are based on the current application.</p>
        </div>
      </div>
    </footer>
  );
}
