import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import AnalyticsPage from "@/app/(app)/analytics/page";

describe("Analytics page", () => {
  it("renders the page hierarchy and honest unavailable overview", () => {
    render(<AnalyticsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Analytics" }),
    ).toBeVisible();
    for (const section of [
      "Reporting period",
      "Overview",
      "Performance",
      "Outcomes",
      "Setup and data trust",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: section }),
      ).toBeVisible();
    }

    const metricCards = screen.getAllByRole("article");
    const metricLabels = [
      "Leads generated",
      "Qualified leads",
      "Conversations",
      "Appointments",
      "AI handled",
      "Human handoffs",
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
    expect(screen.getAllByText("—")).toHaveLength(6);
  });

  it("provides accessible local-only date and filter controls", async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);

    const range = screen.getByRole("combobox", { name: "Date range" });
    const agent = screen.getByRole("combobox", { name: "Agent" });
    const workflow = screen.getByRole("combobox", { name: "Workflow" });
    const channel = screen.getByRole("combobox", { name: "Channel or source" });

    expect(range).toHaveValue("30");
    await user.selectOptions(range, "7");
    await user.selectOptions(agent, "sales");
    await user.selectOptions(workflow, "follow-up");
    await user.selectOptions(channel, "inbox");
    await user.click(screen.getByRole("button", { name: "Clear filters" }));

    expect(range).toHaveValue("30");
    expect(agent).toHaveValue("all");
    expect(workflow).toHaveValue("all");
    expect(channel).toHaveValue("all");
    expect(screen.getByText(/They do not query analytics data/)).toBeVisible();
  });

  it("renders performance and outcome sections as unavailable placeholders", () => {
    render(<AnalyticsPage />);

    for (const title of [
      "Lead performance",
      "Conversation performance",
      "AI agent performance",
      "Workflow performance",
      "Business outcomes",
    ]) {
      expect(screen.getByRole("heading", { name: title })).toBeVisible();
      expect(
        screen.getByRole("img", {
          name: `${title} chart placeholder. Data will appear here.`,
        }),
      ).toBeVisible();
    }

    expect(screen.getAllByText("Data will appear here")).toHaveLength(5);
    expect(
      screen.getAllByText(/No chart series, percentages, or trends/),
    ).toHaveLength(5);
    expect(screen.getAllByText("Data unavailable")).toHaveLength(5);
  });

  it("lists metric concepts without fabricating values", () => {
    render(<AnalyticsPage />);

    for (const metric of [
      "Lead volume",
      "Qualification rate",
      "Conversion rate",
      "Conversation volume",
      "Tasks completed",
      "Workflow runs",
      "Approval rate",
      "Appointments booked",
      "Human interventions",
    ]) {
      expect(screen.getByText(metric)).toBeVisible();
    }

    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.queryByText("42")).not.toBeInTheDocument();
    expect(screen.queryByText("svg")).not.toBeInTheDocument();
  });

  it("explains the empty setup state and related data sources", () => {
    render(<AnalyticsPage />);

    expect(
      screen.getByRole("heading", {
        name: "Analytics will become available as FlowPilot starts processing real business activity",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Transparent visibility" }),
    ).toBeVisible();
    expect(
      screen.getByText(/does not calculate performance, accuracy, attribution/),
    ).toBeVisible();

    const navigation = screen.getByRole("navigation", {
      name: "Explore related workspaces",
    });
    for (const [label, href] of [
      ["Leads", "/leads"],
      ["Conversations", "/inbox"],
      ["Agents", "/agents"],
      ["Workflows", "/workflows"],
      ["Approvals", "/approvals"],
      ["Integrations", "/integrations"],
    ]) {
      expect(
        within(navigation).getByRole("link", { name: label }),
      ).toHaveAttribute("href", href);
    }
  });
});
