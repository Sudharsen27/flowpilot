import {
  Activity,
  BarChart3,
  Bot,
  Building2,
  CheckCheck,
  Columns3,
  Cpu,
  Handshake,
  Inbox,
  LayoutDashboard,
  LibraryBig,
  ListChecks,
  Plug,
  Search,
  Settings,
  Users,
  UsersRound,
  Workflow,
  type LucideIcon,
} from "lucide-react";

import type { MembershipRole } from "@/types/api";

export type NavigationItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Limit visibility to these roles. Omitted: every role (pages enforce read-only). */
  roles?: readonly MembershipRole[];
};

export type NavigationGroup = {
  label: string;
  items: readonly NavigationItem[];
};

export type SecondaryNavigationItem = NavigationItem & {
  status: "available" | "planned";
};

/** Only routes that exist. Contacts and notifications have no backend, so they are absent. */
export const NAV_GROUPS: readonly NavigationGroup[] = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/activity", label: "Activity", icon: Activity },
    ],
  },
  {
    label: "CRM",
    items: [
      { href: "/leads", label: "Leads", icon: Users },
      { href: "/deals", label: "Deals", icon: Handshake },
      { href: "/deals/pipeline", label: "Pipeline", icon: Columns3 },
      { href: "/company-prospects", label: "Company Prospects", icon: Building2 },
      { href: "/prospect-discovery", label: "Prospect Discovery", icon: Search },
      { href: "/inbox", label: "AI Inbox", icon: Inbox },
      { href: "/approvals", label: "Approvals", icon: CheckCheck },
    ],
  },
  {
    label: "Insights",
    items: [
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/agents/executions", label: "Agent runs", icon: ListChecks },
    ],
  },
  {
    label: "Automation",
    items: [
      { href: "/agents", label: "AI Agents", icon: Bot },
      { href: "/workflows", label: "Workflows", icon: Workflow },
      { href: "/knowledge", label: "Knowledge", icon: LibraryBig },
      { href: "/integrations", label: "Integrations", icon: Plug },
    ],
  },
  {
    label: "Administration",
    items: [
      { href: "/settings#team", label: "Team", icon: UsersRound },
      { href: "/settings/ai", label: "AI settings", icon: Cpu },
    ],
  },
];

/** Workspaces that are still being built; shown under "Coming soon". */
export const SECONDARY_NAV_ITEMS: readonly SecondaryNavigationItem[] = [];

export const SETTINGS_ITEM: NavigationItem = {
  href: "/settings",
  label: "Settings",
  icon: Settings,
};

function routeOf(href: string) {
  return href.split("#")[0] ?? href;
}

/** Prefix match: true for the route itself and anything nested under it. */
export function isNavigationItemActive(pathname: string, href: string): boolean {
  const route = routeOf(href);
  return pathname === route || pathname.startsWith(`${route}/`);
}

export function visibleNavigationGroups(
  role: MembershipRole | undefined,
): NavigationGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.roles || (role && item.roles.includes(role))),
  })).filter((group) => group.items.length > 0);
}

function allItems(): NavigationItem[] {
  return [...NAV_GROUPS.flatMap((group) => group.items), ...SECONDARY_NAV_ITEMS, SETTINGS_ITEM];
}

/**
 * The single item to highlight: the longest matching route, so /deals/pipeline
 * marks Pipeline (not Deals too). In-page anchors such as /settings#team never
 * claim the route away from their page.
 */
export function activeNavigationHref(pathname: string): string | null {
  let best: NavigationItem | null = null;
  for (const item of allItems()) {
    if (item.href.includes("#") || !isNavigationItemActive(pathname, item.href)) continue;
    if (!best || routeOf(item.href).length > routeOf(best.href).length) best = item;
  }
  return best?.href ?? null;
}

export function getNavigationItemLabel(pathname: string): string {
  const active = activeNavigationHref(pathname);
  return allItems().find((item) => item.href === active)?.label ?? "FlowPilot";
}

/** Group label for the current page, e.g. "CRM" for /deals. */
export function getNavigationGroupLabel(pathname: string): string | null {
  const active = activeNavigationHref(pathname);
  if (active === SETTINGS_ITEM.href) return "Administration";
  return NAV_GROUPS.find((group) => group.items.some((item) => item.href === active))?.label ?? null;
}
