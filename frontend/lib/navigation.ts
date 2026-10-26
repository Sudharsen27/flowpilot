import {
  Activity,
  BarChart3,
  Bot,
  Building2,
  CheckCheck,
  Inbox,
  LayoutDashboard,
  LibraryBig,
  Plug,
  Search,
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
    items: [
      { href: "/dashboard", label: "Command Center", icon: LayoutDashboard },
      { href: "/activity", label: "Activity", icon: Activity },
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
    ],
  },
  {
    label: "Work",
    items: [
      { href: "/prospect-discovery", label: "Prospect Discovery", icon: Search },
      { href: "/company-prospects", label: "Company Prospects", icon: Building2 },
      { href: "/leads", label: "Leads", icon: Users },
      { href: "/inbox", label: "AI Inbox", icon: Inbox },
      { href: "/approvals", label: "Approvals", icon: CheckCheck },
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
];

/** Workspaces that are still being built; shown under "Coming soon". */
export const SECONDARY_NAV_ITEMS: readonly SecondaryNavigationItem[] = [];

export const SETTINGS_ITEM: NavigationItem = {
  href: "/settings",
  label: "Settings",
  icon: Settings,
};

export function isNavigationItemActive(
  pathname: string,
  href: string,
): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function getNavigationItemLabel(pathname: string): string {
  const items = [
    ...NAV_GROUPS.flatMap((group) => group.items),
    ...SECONDARY_NAV_ITEMS,
    SETTINGS_ITEM,
  ];
  return (
    items.find((item) => isNavigationItemActive(pathname, item.href))?.label ??
    "FlowPilot"
  );
}
