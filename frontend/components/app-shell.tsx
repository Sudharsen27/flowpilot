"use client";

import { Menu, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { Button } from "@/components/ui/button";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const mobileNavRef = useRef<HTMLElement>(null);

  const closeMobileNav = useCallback(() => {
    setMobileNavOpen(false);
    requestAnimationFrame(() => menuButtonRef.current?.focus());
  }, []);

  useEffect(() => {
    if (!mobileNavOpen) {
      return;
    }

    closeButtonRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeMobileNav();
        return;
      }

      if (event.key === "Tab" && mobileNavRef.current) {
        const focusableElements = Array.from(
          mobileNavRef.current.querySelectorAll<HTMLElement>(
            'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
          ),
        );
        const first = focusableElements[0];
        const last = focusableElements.at(-1);

        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [closeMobileNav, mobileNavOpen]);

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
            onClick={closeMobileNav}
          />
          <aside
            ref={mobileNavRef}
            id="mobile-navigation"
            role="dialog"
            aria-modal="true"
            aria-label="Primary navigation"
            className="border-sidebar-border bg-sidebar relative z-50 h-full w-64 border-r shadow-none"
          >
            <div className="flex justify-end p-2">
              <Button
                ref={closeButtonRef}
                variant="ghost"
                size="icon-sm"
                aria-label="Close menu"
                onClick={closeMobileNav}
              >
                <X />
              </Button>
            </div>
            <AppSidebar onNavigate={closeMobileNav} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-border flex items-center gap-3 border-b px-4 py-3 lg:hidden">
          <Button
            ref={menuButtonRef}
            variant="ghost"
            size="icon-sm"
            aria-expanded={mobileNavOpen}
            aria-controls="mobile-navigation"
            aria-label="Open menu"
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu />
          </Button>
          <p className="text-sm font-medium">FlowPilot</p>
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
