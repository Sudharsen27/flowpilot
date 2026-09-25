"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { GlobalSearchEntry } from "@/components/layout/global-search-entry";
import { OrganizationContext } from "@/components/layout/organization-context";
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
    <header className="border-border bg-background sticky top-0 z-30 flex h-14 shrink-0 items-center justify-between gap-3 border-b px-4 sm:px-6 lg:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <div className="lg:hidden">{mobileNavigationTrigger}</div>
        <Link
          href="/"
          className="focus-visible:ring-ring hidden rounded-sm text-sm font-semibold tracking-tight outline-none focus-visible:ring-2 sm:inline lg:hidden"
        >
          FlowPilot
        </Link>
        <span
          aria-current="page"
          className="text-muted-foreground min-w-0 max-w-40 truncate text-sm lg:hidden"
        >
          <span className="sr-only">Current workspace: </span>
          {currentPageLabel}
        </span>
        {session ? (
          <div className="hidden md:block">
            <OrganizationContext organizationName={session.organization.name} />
          </div>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
        <GlobalSearchEntry />
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
