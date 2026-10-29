"use client";

import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import {
  activeNavigationHref,
  SECONDARY_NAV_ITEMS,
  SETTINGS_ITEM,
  type NavigationItem,
  visibleNavigationGroups,
} from "@/lib/navigation";
import { cn } from "@/lib/utils";
import type { MembershipRole } from "@/types/api";

type AppSidebarProps = {
  organizationName?: string;
  role?: MembershipRole;
  onNavigate?: () => void;
  /** Desktop only: icon rail instead of the full sidebar. */
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  /** Account controls rendered at the bottom (the user menu). */
  account?: ReactNode;
};

type SidebarLinkProps = NavigationItem & {
  active: boolean;
  collapsed: boolean;
  onNavigate?: () => void;
  comingSoon?: boolean;
};

function SidebarLink({
  href,
  label,
  icon: Icon,
  active,
  collapsed,
  onNavigate,
  comingSoon = false,
}: SidebarLinkProps) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      aria-label={
        comingSoon ? `${label} (coming soon)` : collapsed ? label : undefined
      }
      title={
        comingSoon
          ? `${label} is still being built`
          : collapsed
            ? label
            : undefined
      }
      className={cn(
        "group relative flex h-7 items-center rounded-md text-[0.8125rem] transition-colors outline-none",
        "focus-visible:ring-sidebar-ring focus-visible:ring-2",
        collapsed ? "justify-center px-0" : "gap-2.5 px-2",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
          : comingSoon
            ? "text-foreground-disabled hover:bg-muted hover:text-muted-foreground"
            : "text-sidebar-foreground/80 hover:bg-muted hover:text-foreground",
      )}
    >
      {active && !collapsed ? (
        <span
          aria-hidden="true"
          className="bg-sidebar-primary absolute top-1.5 bottom-1.5 -left-3 w-0.5 rounded-r"
        />
      ) : null}
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
      {collapsed ? null : <span className="truncate">{label}</span>}
      {comingSoon && !collapsed ? (
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

export function AppSidebar({
  organizationName,
  role,
  onNavigate,
  collapsed = false,
  onToggleCollapsed,
  account,
}: AppSidebarProps) {
  const pathname = usePathname();
  const active = activeNavigationHref(pathname);
  const groups = visibleNavigationGroups(role);
  const initial = (organizationName?.trim()[0] ?? "F").toUpperCase();

  return (
    <div className="bg-sidebar text-sidebar-foreground flex h-full flex-col">
      <div
        className={cn(
          "flex h-12 items-center",
          collapsed ? "justify-center px-2" : "px-3",
        )}
      >
        <Link
          href="/dashboard"
          onClick={onNavigate}
          aria-label="FlowPilot home"
          title={collapsed ? (organizationName ?? "FlowPilot") : undefined}
          className={cn(
            "hover:bg-muted focus-visible:ring-sidebar-ring flex min-w-0 items-center rounded-md outline-none focus-visible:ring-2",
            collapsed ? "p-1" : "w-full gap-2.5 px-2 py-1.5",
          )}
        >
          <span className="bg-brand text-brand-foreground flex size-7 shrink-0 items-center justify-center rounded-md text-xs font-semibold">
            {initial}
          </span>
          {collapsed ? (
            <span className="sr-only">{organizationName ?? "FlowPilot"}</span>
          ) : (
            <span className="min-w-0">
              <span className="block truncate text-sm leading-4 font-semibold">
                {organizationName ?? "FlowPilot"}
              </span>
              <span className="text-muted-foreground block text-[0.6875rem] leading-4">
                FlowPilot
              </span>
            </span>
          )}
        </Link>
      </div>
      <nav
        aria-label="Primary"
        className={cn(
          "flex flex-1 flex-col gap-3 overflow-y-auto pt-1 pb-2",
          collapsed ? "px-2" : "px-3",
        )}
      >
        {groups.map((group) => (
          <div key={group.label}>
            {collapsed ? (
              <span className="sr-only">{group.label}</span>
            ) : (
              <p className="text-muted-foreground mb-0.5 px-2 text-[0.6875rem] leading-5 font-medium tracking-wide uppercase">
                {group.label}
              </p>
            )}
            <div className="flex flex-col gap-px">
              {group.items.map((item) => (
                <SidebarLink
                  key={item.href}
                  {...item}
                  collapsed={collapsed}
                  active={item.href === active}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          </div>
        ))}
        {SECONDARY_NAV_ITEMS.length > 0 ? (
          <div>
            {collapsed ? null : (
              <p className="text-muted-foreground mb-1 px-2 text-xs font-medium">
                Coming soon
              </p>
            )}
            <div className="flex flex-col gap-px">
              {SECONDARY_NAV_ITEMS.map((item) => (
                <SidebarLink
                  key={item.href}
                  href={item.href}
                  label={item.label}
                  icon={item.icon}
                  comingSoon
                  collapsed={collapsed}
                  active={item.href === active}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          </div>
        ) : null}
      </nav>
      <div
        className={cn(
          "border-sidebar-border grid gap-1 border-t py-1.5",
          collapsed ? "px-2" : "px-3",
        )}
      >
        {/* Settings and the collapse toggle share a row so the menu fits without scrolling. */}
        <div
          className={cn("flex gap-1", collapsed ? "flex-col" : "items-center")}
        >
          <div className="min-w-0 flex-1">
            <SidebarLink
              {...SETTINGS_ITEM}
              collapsed={collapsed}
              active={SETTINGS_ITEM.href === active}
              onNavigate={onNavigate}
            />
          </div>
          {onToggleCollapsed ? (
            <button
              type="button"
              onClick={onToggleCollapsed}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className={cn(
                "text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-sidebar-ring flex h-7 shrink-0 items-center justify-center rounded-md outline-none focus-visible:ring-2",
                collapsed ? "w-full" : "w-7",
              )}
            >
              {collapsed ? (
                <PanelLeftOpen className="size-4" aria-hidden="true" />
              ) : (
                <PanelLeftClose className="size-4" aria-hidden="true" />
              )}
            </button>
          ) : null}
        </div>
        {account ? (
          <div
            className={cn(
              "pt-1",
              collapsed ? "flex justify-center" : undefined,
            )}
          >
            {account}
          </div>
        ) : null}
      </div>
    </div>
  );
}
