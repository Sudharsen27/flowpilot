"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { BrandLockup } from "@/components/brand-lockup";
import { Separator } from "@/components/ui/separator";
import {
  isNavigationItemActive,
  NAV_GROUPS,
  SECONDARY_NAV_ITEMS,
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
  comingSoon?: boolean;
};

function SidebarLink({
  href,
  label,
  icon: Icon,
  active,
  onNavigate,
  comingSoon = false,
}: SidebarLinkProps) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      aria-label={comingSoon ? `${label} (coming soon)` : undefined}
      title={comingSoon ? `${label} is still being built` : undefined}
      className={cn(
        "group flex min-h-9 items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors outline-none",
        "focus-visible:ring-ring focus-visible:ring-2",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-card font-medium"
          : comingSoon
            ? "text-foreground-disabled hover:bg-sidebar-accent/70 hover:text-muted-foreground"
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
      {comingSoon ? (
        <span
          aria-hidden="true"
          className="border-border text-muted-foreground ml-auto rounded border px-1.5 py-px text-[0.625rem] font-medium tracking-wide uppercase"
        >
          Soon
        </span>
      ) : null}
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
          className="focus-visible:ring-ring rounded-md outline-none focus-visible:ring-2"
        >
          <BrandLockup size="sm" />
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
        {SECONDARY_NAV_ITEMS.length > 0 ? (
          <div>
            <p className="text-muted-foreground mb-1.5 px-2.5 text-[0.6875rem] font-medium tracking-wide uppercase">
              Coming soon
            </p>
            <div className="flex flex-col gap-0.5">
              {SECONDARY_NAV_ITEMS.map((item) => (
                <SidebarLink
                  key={item.href}
                  href={item.href}
                  label={item.label}
                  icon={item.icon}
                  comingSoon
                  active={isNavigationItemActive(pathname, item.href)}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          </div>
        ) : null}
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
