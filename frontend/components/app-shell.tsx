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
import { ApplicationTopBar } from "@/components/layout/application-top-bar";
import { PageContainer } from "@/components/layout/page-container";
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
    const previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

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
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousBodyOverflow;
    };
  }, [closeMobileNav, mobileNavOpen]);

  return (
    <div className="bg-background flex min-h-screen">
      <a
        href="#main"
        className="focus:bg-background focus:shadow-overlay sr-only z-[60] focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:rounded-md focus:px-3 focus:py-2 focus:text-sm"
      >
        Skip to content
      </a>
      <aside className="border-sidebar-border sticky top-0 hidden h-screen w-64 shrink-0 border-r lg:block">
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
            className="border-sidebar-border bg-sidebar shadow-overlay relative z-50 h-full w-72 max-w-[85vw] border-r"
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
        <ApplicationTopBar
          mobileNavigationTrigger={
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
          }
        />
        <main id="main" className="flex-1 py-6 sm:py-8">
          <PageContainer size="wide">{children}</PageContainer>
        </main>
      </div>
    </div>
  );
}
