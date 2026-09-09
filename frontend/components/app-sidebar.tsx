"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Separator } from "@/components/ui/separator";
import {
  isNavigationItemActive,
  NAV_GROUPS,
  SETTINGS_ITEM,
  type NavigationItem,
} from "@/lib/navigation";
import { cn } from "@/lib/utils";

type AppSidebarProps = {
  onNavigate?: () => void;
};

type SidebarLinkProps = NavigationItem & {
  active: boolean;
  onNavigate?: () => void;
};

function SidebarLink({
  href,
  label,
  icon: Icon,
  active,
  onNavigate,
}: SidebarLinkProps) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex min-h-9 items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors outline-none",
        "focus-visible:ring-ring focus-visible:ring-2",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-card font-medium"
          : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground",
      )}
    >
      <Icon
        className={cn(
          "size-4 shrink-0",
          active
            ? "text-sidebar-primary"
            : "text-muted-foreground group-hover:text-foreground",
        )}
        strokeWidth={1.8}
        aria-hidden="true"
      />
      {label}
    </Link>
  );
}

export function AppSidebar({ onNavigate }: AppSidebarProps) {
  const pathname = usePathname();

  return (
    <div className="bg-sidebar text-sidebar-foreground flex h-full flex-col">
      <div className="px-4 py-4">
        <Link
          href="/"
          onClick={onNavigate}
          aria-label="FlowPilot home"
          className="focus-visible:ring-ring flex items-center gap-2.5 rounded-md outline-none focus-visible:ring-2"
        >
          <span className="bg-primary text-primary-foreground flex size-8 items-center justify-center rounded-md text-sm font-semibold">
            F
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold tracking-tight">
              FlowPilot
            </span>
            <span className="text-muted-foreground block text-[0.6875rem] leading-4">
              Business operations
            </span>
          </span>
        </Link>
      </div>
      <Separator />
      <nav
        aria-label="Primary"
        className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4"
      >
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <p className="text-muted-foreground mb-1.5 px-2.5 text-[0.6875rem] font-medium tracking-wide uppercase">
              {group.label}
            </p>
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) => (
                <SidebarLink
                  key={item.href}
                  {...item}
                  active={isNavigationItemActive(pathname, item.href)}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="px-3 py-3">
        <Separator className="mb-3" />
        <SidebarLink
          {...SETTINGS_ITEM}
          active={isNavigationItemActive(pathname, SETTINGS_ITEM.href)}
          onNavigate={onNavigate}
        />
      </div>
    </div>
  );
}
