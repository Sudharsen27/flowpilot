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

export const NAV_GROUPS: readonly NavigationGroup[] = [
  {
    label: "Overview",
    items: [{ href: "/", label: "Command Center", icon: LayoutDashboard }],
  },
  {
    label: "Automation",
    items: [
      { href: "/agents", label: "AI Agents", icon: Bot },
      { href: "/workflows", label: "Workflows", icon: Workflow },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/leads", label: "Leads", icon: Users },
      { href: "/inbox", label: "AI Inbox", icon: Inbox },
      { href: "/knowledge", label: "Knowledge", icon: LibraryBig },
      { href: "/approvals", label: "Approvals", icon: CheckCheck },
    ],
  },
  {
    label: "Workspace",
    items: [
      { href: "/integrations", label: "Integrations", icon: Plug },
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/activity", label: "Activity", icon: Activity },
    ],
  },
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
