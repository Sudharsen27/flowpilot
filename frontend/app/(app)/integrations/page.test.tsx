import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import IntegrationsPage from "@/app/(app)/integrations/page";
import { IntegrationStatusBadge } from "@/components/integrations/integration-status-badge";

describe("Integrations page", () => {
  it("renders the page hierarchy and honest unavailable overview", () => {
    render(<IntegrationsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Integrations" }),
    ).toBeVisible();
    for (const section of [
      "Integration overview",
      "Connection status",
      "Integration catalog",
      "Integration setup",
      "Agents, workflows, and trust",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: section }),
      ).toBeVisible();
    }

    const metricCards = screen.getAllByRole("article").slice(0, 4);
    const metricLabels = [
      "Connected",
      "Available",
      "Needs attention",
      "Data sources",
    ];
    expect(metricCards).toHaveLength(metricLabels.length);
    metricLabels.forEach((label, index) => {
      expect(
        within(metricCards[index]).getByRole("heading", {
          level: 3,
          name: label,
        }),
      ).toBeVisible();
    });
    expect(screen.getAllByText("—")).toHaveLength(4);
  });

  it("shows an honest zero-connection state with valid navigation", () => {
    render(<IntegrationsPage />);

    expect(
      screen.getByRole("heading", { name: "No tools connected" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        /Integration support and secure connection flows are not implemented/,
      ),
    ).toBeVisible();
    const navigation = screen.getByRole("navigation", {
      name: "Explore automation workspaces",
    });
    expect(
      within(navigation).getByRole("link", { name: "AI Agents" }),
    ).toHaveAttribute("href", "/agents");
    expect(
      within(navigation).getByRole("link", { name: "Workflows" }),
    ).toHaveAttribute("href", "/workflows");
  });

  it("renders a planned catalog without claiming connected support", () => {
    render(<IntegrationsPage />);

    const catalog = screen.getByRole("list", {
      name: "Integration catalog",
    });
    expect(within(catalog).getAllByRole("listitem")).toHaveLength(11);
    for (const integration of [
      "Salesforce",
      "HubSpot",
      "Pipedrive",
      "Gmail",
      "Outlook",
      "Slack",
      "WhatsApp",
      "Google Calendar",
      "Microsoft Outlook Calendar",
      "Webhooks",
      "REST API",
    ]) {
      expect(
        within(catalog).getByRole("heading", { name: integration }),
      ).toBeVisible();
    }
    expect(
      within(catalog).getAllByRole("button", { name: "Coming soon" }),
    ).toHaveLength(11);
    within(catalog)
      .getAllByRole("button", { name: "Coming soon" })
      .forEach((button) => expect(button).toBeDisabled());
    expect(catalog.querySelector('[data-status="active"]')).toBeNull();
  });

  it("searches and filters catalog concepts locally", async () => {
    const user = userEvent.setup();
    render(<IntegrationsPage />);

    const search = screen.getByRole("searchbox", {
      name: "Search integrations",
    });
    const category = screen.getByRole("combobox", {
      name: "Integration category",
    });
    const status = screen.getByRole("combobox", {
      name: "Connection status",
    });

    await user.type(search, "HubSpot");
    expect(screen.getByRole("heading", { name: "HubSpot" })).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Salesforce" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear search" }));
    await user.selectOptions(category, "calendar");
    expect(
      screen.getByRole("heading", { name: "Google Calendar" }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Microsoft Outlook Calendar" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Gmail" }),
    ).not.toBeInTheDocument();

    await user.selectOptions(status, "connected");
    expect(
      screen.getByRole("heading", { name: "No catalog concepts match" }),
    ).toBeVisible();
    expect(screen.getByText(/No integration data was queried/)).toBeVisible();
  });

  it("keeps setup and credential behavior unavailable", () => {
    render(<IntegrationsPage />);

    expect(
      screen.getByRole("heading", { name: "Integration setup preview" }),
    ).toBeVisible();
    for (const concept of [
      "Permissions",
      "Data access",
      "Configuration requirements",
    ]) {
      expect(screen.getByText(concept)).toBeVisible();
    }
    expect(
      screen.getByText("No credentials are requested or stored by this UI."),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Configure connection" }),
    ).toBeDisabled();
  });

  it("renders the conceptual agent/workflow connection and trust boundary", () => {
    render(<IntegrationsPage />);

    const connection = screen.getByRole("list", {
      name: "Conceptual integration connection",
    });
    expect(within(connection).getAllByRole("listitem")).toHaveLength(4);
    for (const step of [
      "Business tools",
      "Integrations",
      "FlowPilot agents",
      "Workflows / actions",
    ]) {
      expect(within(connection).getByText(step)).toBeVisible();
    }
    expect(
      screen.getByRole("heading", { name: "Permissions and control" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        /No connection, credential, token, or permission enforcement/,
      ),
    ).toBeVisible();
  });

  it("maps all possible connection statuses to clear labels", () => {
    render(
      <>
        <IntegrationStatusBadge status="connected" />
        <IntegrationStatusBadge status="not-connected" />
        <IntegrationStatusBadge status="needs-attention" />
        <IntegrationStatusBadge status="coming-soon" />
      </>,
    );

    for (const label of [
      "Connected",
      "Not connected",
      "Needs attention",
      "Coming soon",
    ]) {
      expect(screen.getByText(label)).toBeVisible();
    }
  });

  it("uses an adaptive catalog grid", () => {
    render(<IntegrationsPage />);

    expect(
      screen.getByRole("list", { name: "Integration catalog" }),
    ).toHaveClass("grid", "sm:grid-cols-2", "xl:grid-cols-3");
  });
});
