"use client";

import { Menu, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { ApplicationTopBar } from "@/components/layout/application-top-bar";
import { PageContainer } from "@/components/layout/page-container";
import { UserMenu } from "@/components/layout/user-menu";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";

type AppShellProps = {
  children: ReactNode;
};

const SIDEBAR_COLLAPSED_KEY = "flowpilot.sidebar.collapsed";
const SIDEBAR_EVENT = "flowpilot:sidebar-collapsed";

// A per-browser convenience in localStorage; every read and write tolerates blocked storage.
function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

function writeCollapsed(value: boolean) {
  try {
    window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, value ? "1" : "0");
  } catch {
    // Storage unavailable (e.g. private mode): the preference is not remembered.
  }
  window.dispatchEvent(new Event(SIDEBAR_EVENT));
}

function subscribeCollapsed(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(SIDEBAR_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(SIDEBAR_EVENT, onChange);
  };
}

export function AppShell({ children }: AppShellProps) {
  const { session, signOut } = useAuth();
  const organizationName = session?.organization.name;
  const role = session?.membership.role;
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const collapsed = useSyncExternalStore(
    subscribeCollapsed,
    readCollapsed,
    () => false,
  );
  const toggleCollapsed = useCallback(
    () => writeCollapsed(!readCollapsed()),
    [],
  );

  function account(collapsedMenu: boolean) {
    return session ? (
      <UserMenu
        user={session.user}
        organizationName={session.organization.name}
        role={session.membership.role}
        onSignOut={signOut}
        variant="sidebar"
        collapsed={collapsedMenu}
      />
    ) : null;
  }
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
      <div
        aria-hidden={mobileNavOpen || undefined}
        inert={mobileNavOpen || undefined}
        data-slot="app-content"
        className="flex min-w-0 flex-1"
      >
        <a
          href="#main"
          className="focus:bg-background focus:shadow-overlay sr-only z-[60] focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:rounded-md focus:px-3 focus:py-2 focus:text-sm"
        >
          Skip to content
        </a>
        <aside
          className={cn(
            "border-sidebar-border bg-sidebar sticky top-0 hidden h-screen shrink-0 border-r motion-safe:transition-[width] motion-safe:duration-200 lg:block",
            collapsed ? "w-16" : "w-60",
          )}
        >
          <AppSidebar
            organizationName={organizationName}
            role={role}
            collapsed={collapsed}
            onToggleCollapsed={toggleCollapsed}
            account={account(collapsed)}
          />
        </aside>

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
          <main id="main" className="flex-1 py-5 sm:py-6">
            <PageContainer size="wide">{children}</PageContainer>
          </main>
        </div>
      </div>

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
            <AppSidebar
              organizationName={organizationName}
              role={role}
              onNavigate={closeMobileNav}
              account={account(false)}
            />
          </aside>
        </div>
      ) : null}
    </div>
  );
}
