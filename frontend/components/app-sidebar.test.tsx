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
