import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppSidebar } from "@/components/app-sidebar";
import {
  activeNavigationHref,
  getNavigationGroupLabel,
  getNavigationItemLabel,
  NAV_GROUPS,
  visibleNavigationGroups,
} from "@/lib/navigation";

let pathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
}));

describe("application sidebar navigation", () => {
  beforeEach(() => {
    pathname = "/";
  });

  it("marks only the exact current route as active", () => {
    pathname = "/agents";
    render(<AppSidebar />);

    expect(screen.getByRole("link", { name: "AI Agents" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("link", { name: "Dashboard" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("shows the daily workspaces, including Activity", () => {
    render(<AppSidebar />);

    for (const label of [
      "Dashboard",
      "Activity",
      "Analytics",
      "Leads",
      "Deals",
      "AI Inbox",
      "Approvals",
      "AI Agents",
      "Workflows",
      "Knowledge",
      "Integrations",
      "Settings",
    ]) {
      expect(screen.getByRole("link", { name: label })).toBeVisible();
    }
  });

  it("hides the coming soon group once every module is live", () => {
    render(<AppSidebar />);

    expect(screen.queryByText("Coming soon")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /coming soon/ }),
    ).not.toBeInTheDocument();
    for (const label of ["Workflows", "Integrations"]) {
      expect(screen.getByRole("link", { name: label })).toBeVisible();
    }
  });

  it("shows the current organization at the top", () => {
    render(<AppSidebar organizationName="Northstar Operations" />);

    expect(
      screen.getByRole("link", { name: "FlowPilot home" }),
    ).toHaveTextContent("Northstar Operations");
    expect(
      screen.getByRole("link", { name: "FlowPilot home" }),
    ).toHaveAttribute("href", "/dashboard");
  });

  it("keeps the parent item active for a nested route", () => {
    pathname = "/agents/agent-id";
    render(<AppSidebar />);

    expect(screen.getByRole("link", { name: "AI Agents" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    const currentLinks = screen
      .getAllByRole("link")
      .filter((link) => link.getAttribute("aria-current") === "page");
    expect(currentLinks).toHaveLength(1);
  });

  it("marks only the most specific item, so Pipeline wins over Deals", () => {
    pathname = "/deals/pipeline";
    render(<AppSidebar />);
    expect(screen.getByRole("link", { name: "Pipeline" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Deals" })).not.toHaveAttribute("aria-current");
    expect(activeNavigationHref("/deals/deal-1")).toBe("/deals");
    expect(activeNavigationHref("/agents/executions")).toBe("/agents/executions");
    expect(activeNavigationHref("/settings")).toBe("/settings");
    expect(activeNavigationHref("/settings/ai")).toBe("/settings/ai");
    expect(getNavigationItemLabel("/deals/targets")).toBe("Deals");
    expect(getNavigationGroupLabel("/deals/pipeline")).toBe("CRM");
    expect(getNavigationGroupLabel("/settings")).toBe("Administration");
  });

  it("only links to routes that exist (no Contacts or notifications)", () => {
    const hrefs = NAV_GROUPS.flatMap((group) => group.items.map((item) => item.href));
    expect(hrefs).not.toContain("/contacts");
    expect(hrefs).not.toContain("/notifications");
    expect(hrefs).toEqual(expect.arrayContaining(["/dashboard", "/deals", "/deals/pipeline"]));
  });

  it("keeps accessible names in the collapsed icon rail and toggles", async () => {
    const onToggle = vi.fn();
    render(<AppSidebar collapsed onToggleCollapsed={onToggle} />);
    expect(screen.getByRole("link", { name: "Deals" })).toHaveAttribute("title", "Deals");
    expect(screen.queryByText("CRM")).toHaveClass("sr-only");
    screen.getByRole("button", { name: "Expand sidebar" }).click();
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("filters items by role when an item declares roles", () => {
    const groups = visibleNavigationGroups("MEMBER");
    expect(groups.flatMap((group) => group.items).length).toBe(
      NAV_GROUPS.flatMap((group) => group.items).filter((item) => !item.roles?.length || item.roles.includes("MEMBER")).length,
    );
  });

  it("renders account controls at the bottom", () => {
    render(<AppSidebar account={<button type="button">Account</button>} />);
    expect(screen.getByRole("button", { name: "Account" })).toBeInTheDocument();
  });
});
