import {
  Activity,
  BarChart3,
  Bot,
  CheckCheck,
  Inbox,
  LayoutDashboard,
  LibraryBig,
  Plug,
  Settings,
  Users,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export type NavigationItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export type NavigationGroup = {
  label: string;
  items: readonly NavigationItem[];
};

export type SecondaryNavigationItem = NavigationItem & {
  status: "available" | "planned";
};

export const NAV_GROUPS: readonly NavigationGroup[] = [
  {
    label: "Overview",
    items: [{ href: "/", label: "Command Center", icon: LayoutDashboard }],
  },
  {
    label: "Work",
    items: [
      { href: "/leads", label: "Leads", icon: Users },
      { href: "/inbox", label: "AI Inbox", icon: Inbox },
      { href: "/approvals", label: "Approvals", icon: CheckCheck },
    ],
  },
  {
    label: "Automation",
    items: [{ href: "/agents", label: "AI Agents", icon: Bot }],
  },
];

/** Reachable routes that are not part of the daily sidebar. */
export const SECONDARY_NAV_ITEMS: readonly SecondaryNavigationItem[] = [
  { href: "/activity", label: "Activity", icon: Activity, status: "available" },
  { href: "/workflows", label: "Workflows", icon: Workflow, status: "planned" },
  {
    href: "/knowledge",
    label: "Knowledge",
    icon: LibraryBig,
    status: "planned",
  },
  {
    href: "/integrations",
    label: "Integrations",
    icon: Plug,
    status: "planned",
  },
  { href: "/analytics", label: "Analytics", icon: BarChart3, status: "planned" },
];

export const SETTINGS_ITEM: NavigationItem = {
  href: "/settings",
  label: "Settings",
  icon: Settings,
};

export function isNavigationItemActive(
  pathname: string,
  href: string,
): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function getNavigationItemLabel(pathname: string): string {
  const items = [
    ...NAV_GROUPS.flatMap((group) => group.items),
    ...SECONDARY_NAV_ITEMS,
    SETTINGS_ITEM,
  ];
  return items.find((item) => isNavigationItemActive(pathname, item.href))?.label ?? "FlowPilot";
}
