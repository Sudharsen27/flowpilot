"use client";

import { ArrowRight, Menu, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { BrandLockup } from "@/components/brand-lockup";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "#product", label: "Product" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#pricing", label: "Pricing" },
  { href: "#trust", label: "Trust" },
] as const;

export function MarketingHeader() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  return (
    <header className="border-border/70 bg-background/90 sticky top-0 z-50 border-b backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Link
          href="/"
          aria-label="FlowPilot home"
          onClick={() => setOpen(false)}
        >
          <BrandLockup size="sm" />
        </Link>

        <nav
          aria-label="Marketing"
          className="hidden items-center gap-1 md:flex"
        >
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-muted-foreground hover:text-foreground rounded-lg px-3 py-2 text-sm font-medium transition-colors"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <ThemeToggle />
          <Link
            href="/login"
            className={buttonVariants({ variant: "ghost", size: "lg" })}
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className={buttonVariants({ size: "lg", className: "px-4" })}
          >
            Get started
            <ArrowRight aria-hidden="true" />
          </Link>
        </div>

        <div className="flex items-center gap-1 md:hidden">
          <ThemeToggle />
          <button
            type="button"
            className="hover:bg-muted inline-flex size-11 items-center justify-center rounded-lg"
            aria-label={open ? "Close navigation" : "Open navigation"}
            aria-expanded={open}
            aria-controls="marketing-mobile-menu"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
          </button>
        </div>
      </div>

      <div
        id="marketing-mobile-menu"
        className={cn(
          "border-border bg-background absolute inset-x-0 top-full border-b p-4 shadow-lg md:hidden",
          open ? "grid" : "hidden",
        )}
      >
        <nav aria-label="Mobile marketing" className="grid gap-1">
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="hover:bg-muted rounded-lg px-3 py-3 text-base font-medium"
              onClick={() => setOpen(false)}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="border-border mt-4 grid grid-cols-2 gap-2 border-t pt-4">
          <Link
            href="/login"
            className={buttonVariants({ variant: "outline", size: "lg" })}
            onClick={() => setOpen(false)}
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className={buttonVariants({ size: "lg" })}
            onClick={() => setOpen(false)}
          >
            Get started
          </Link>
        </div>
      </div>
    </header>
  );
}
