"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { CommandLauncher } from "@/components/layout/command-launcher";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { UserMenu } from "@/components/layout/user-menu";
import { useAuth } from "@/hooks/use-auth";
import { getNavigationItemLabel } from "@/lib/navigation";

type ApplicationTopBarProps = {
  mobileNavigationTrigger: ReactNode;
};

export function ApplicationTopBar({
  mobileNavigationTrigger,
}: ApplicationTopBarProps) {
  const { session, signOut } = useAuth();
  const pathname = usePathname();
  const currentPageLabel = getNavigationItemLabel(pathname);

  return (
    <header className="border-border bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b px-4 backdrop-blur sm:px-6 lg:px-8">
      <div className="lg:hidden">{mobileNavigationTrigger}</div>
      <span
        aria-current="page"
        className="min-w-0 max-w-40 truncate text-sm font-medium lg:hidden"
      >
        <span className="sr-only">Current workspace: </span>
        {currentPageLabel}
      </span>
      <div className="flex min-w-0 flex-1 justify-end lg:justify-start">
        <CommandLauncher />
      </div>
      <div className="flex shrink-0 items-center gap-1 sm:gap-1.5">
        <ThemeToggle />
        {session ? (
          <UserMenu
            user={session.user}
            organizationName={session.organization.name}
            role={session.membership.role}
            onSignOut={signOut}
          />
        ) : null}
      </div>
    </header>
  );
}
