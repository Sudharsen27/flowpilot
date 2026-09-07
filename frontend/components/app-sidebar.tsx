"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Separator } from "@/components/ui/separator";
import { NAV_ITEMS, SETTINGS_ITEM } from "@/lib/navigation";
import { cn } from "@/lib/utils";

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

type AppSidebarProps = {
  onNavigate?: () => void;
};

export function AppSidebar({ onNavigate }: AppSidebarProps) {
  const pathname = usePathname();

  return (
    <div className="bg-sidebar text-sidebar-foreground flex h-full flex-col">
      <div className="px-5 py-5">
        <p className="text-sm font-semibold tracking-tight">Automation</p>
        <p className="text-muted-foreground mt-0.5 text-xs">
          Business workspace
        </p>
      </div>
      <Separator />
      <nav
        aria-label="Primary"
        className="flex flex-1 flex-col gap-1 px-3 py-4"
      >
        {NAV_ITEMS.map((item) => {
          const active = isActivePath(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-2 text-sm transition-colors outline-none",
                "focus-visible:ring-ring focus-visible:ring-2",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                  : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="px-3 pb-4">
        <Separator className="mb-3" />
        <Link
          href={SETTINGS_ITEM.href}
          onClick={onNavigate}
          aria-current={
            isActivePath(pathname, SETTINGS_ITEM.href) ? "page" : undefined
          }
          className={cn(
            "block rounded-md px-3 py-2 text-sm transition-colors outline-none",
            "focus-visible:ring-ring focus-visible:ring-2",
            isActivePath(pathname, SETTINGS_ITEM.href)
              ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
              : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground",
          )}
        >
          {SETTINGS_ITEM.label}
        </Link>
      </div>
    </div>
  );
}
