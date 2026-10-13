import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppSidebar } from "@/components/app-sidebar";

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
      screen.getByRole("link", { name: "Command Center" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("shows the daily workspaces, including Activity", () => {
    render(<AppSidebar />);

    for (const label of [
      "Command Center",
      "Activity",
      "Analytics",
      "Leads",
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
});
