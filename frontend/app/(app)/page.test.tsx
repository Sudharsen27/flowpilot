import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import CommandCenterPage from "@/app/(app)/page";

describe("Command Center", () => {
  it("renders the dashboard and its major sections", () => {
    render(<CommandCenterPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Command Center" }),
    ).toBeVisible();
    for (const heading of [
      "Business overview",
      "AI workforce",
      "Needs attention",
      "Recent activity",
      "Quick actions",
    ]) {
      expect(screen.getByRole("heading", { name: heading })).toBeVisible();
    }
  });

  it("presents unavailable business and agent states honestly", () => {
    render(<CommandCenterPage />);

    const metricCards = screen.getAllByRole("article");
    const metricLabels = [
      "Leads",
      "Conversations",
      "Appointments",
      "Pending approvals",
    ];
    expect(metricCards).toHaveLength(metricLabels.length);
    metricLabels.forEach((metric, index) => {
      expect(
        within(metricCards[index]).getByRole("heading", {
          level: 3,
          name: metric,
        }),
      ).toBeVisible();
    });
    expect(screen.getAllByText("—")).toHaveLength(4);
    expect(screen.getByText("Connect a lead source")).toBeVisible();
    expect(screen.getByText("No conversation data")).toBeVisible();
    expect(screen.getByText("No appointment data")).toBeVisible();
    expect(screen.getByText("No approval data")).toBeVisible();
    expect(screen.getByText("Not configured")).toHaveAttribute(
      "data-status",
      "draft",
    );
    expect(
      screen.getByText(/No live agent runtime is connected yet/),
    ).toBeVisible();
    expect(screen.getByText(/Nothing requires your review yet/)).toBeVisible();
    expect(
      screen.getByText(/No business activity is available yet/),
    ).toBeVisible();
  });

  it("links quick actions only to valid product routes", () => {
    render(<CommandCenterPage />);

    const hrefs = screen
      .getAllByRole("link")
      .map((link) => link.getAttribute("href"));

    for (const href of [
      "/agents",
      "/leads",
      "/inbox",
      "/approvals",
      "/workflows",
    ]) {
      expect(hrefs).toContain(href);
    }
    expect(hrefs.every((href) => href?.startsWith("/"))).toBe(true);
  });
});
