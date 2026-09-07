"use client";

import { useState, type ReactNode } from "react";
import { Menu, X } from "lucide-react";

import { AppSidebar } from "@/components/app-sidebar";
import { Button } from "@/components/ui/button";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="bg-background flex min-h-full">
      <aside className="border-sidebar-border hidden w-60 shrink-0 border-r lg:block">
        <AppSidebar />
      </aside>

      {mobileNavOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="bg-foreground/20 absolute inset-0"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside className="border-sidebar-border bg-sidebar relative z-50 h-full w-64 border-r shadow-none">
            <div className="flex justify-end p-2">
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label="Close menu"
                onClick={() => setMobileNavOpen(false)}
              >
                <X />
              </Button>
            </div>
            <AppSidebar onNavigate={() => setMobileNavOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-border flex items-center gap-3 border-b px-4 py-3 lg:hidden">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-expanded={mobileNavOpen}
            aria-controls="mobile-navigation"
            aria-label="Open menu"
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu />
          </Button>
          <p className="text-sm font-medium">Automation</p>
        </header>
        <a
          href="#main"
          className="focus:bg-background sr-only focus:not-sr-only focus:absolute focus:m-3 focus:rounded-md focus:px-3 focus:py-2 focus:text-sm"
        >
          Skip to content
        </a>
        <main id="main" className="flex-1 px-4 py-8 sm:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
