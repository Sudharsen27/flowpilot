import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import LeadsPage from "@/app/(app)/leads/page";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { LeadsTable, type LeadListItem } from "@/components/leads/leads-table";
import { QualificationStatus } from "@/components/leads/qualification-status";

describe("Leads page", () => {
  it("renders the page hierarchy and honest unavailable metrics", () => {
    render(<LeadsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Leads" }),
    ).toBeVisible();
    for (const section of [
      "Lead overview",
      "Lead directory",
      "AI qualification",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: section }),
      ).toBeVisible();
    }

    const metricCards = screen.getAllByRole("article");
    const metricLabels = [
      "Total leads",
      "New leads",
      "Qualified leads",
      "Follow-up required",
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

  it("provides accessible, locally resettable search and filters", async () => {
    const user = userEvent.setup();
    render(<LeadsPage />);

    const search = screen.getByRole("searchbox", { name: "Search leads" });
    const status = screen.getByRole("combobox", { name: "Lead status" });
    const source = screen.getByRole("combobox", { name: "Lead source" });
    const qualification = screen.getByRole("combobox", {
      name: "AI qualification",
    });

    expect(search).toBeVisible();
    expect(status).toHaveValue("all");
    expect(source).toHaveValue("all");
    expect(qualification).toHaveValue("all");

    await user.type(search, "Example");
    await user.selectOptions(status, "new");
    await user.selectOptions(source, "form");
    await user.selectOptions(qualification, "not-assessed");

    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(search).toHaveValue("");
    expect(status).toHaveValue("all");
    expect(source).toHaveValue("all");
    expect(qualification).toHaveValue("all");
  });

  it("shows setup states without rendering fabricated lead rows", () => {
    render(<LeadsPage />);

    expect(screen.getByRole("heading", { name: "No leads yet" })).toBeVisible();
    expect(
      screen.getByText(/forms, inboxes, or integrations are connected/),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", {
        name: "AI qualification is not connected",
      }),
    ).toBeVisible();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("Example")).not.toBeInTheDocument();
  });

  it("maps typed lead and qualification states to visible text", () => {
    render(
      <>
        <LeadStatusBadge status="contacted" />
        <QualificationStatus status="not-assessed" />
      </>,
    );

    expect(screen.getByText("Contacted")).toBeVisible();
    expect(screen.getByText("Not assessed")).toBeVisible();
    expect(screen.queryByText(/\/100/)).not.toBeInTheDocument();
  });

  it("supports desktop table and mobile list representations for real rows", () => {
    const lead: LeadListItem = {
      id: "lead-1",
      name: "Test lead",
      email: "lead@example.com",
      company: "Test company",
      status: "new",
      qualification: { status: "unavailable" },
      source: "Website form",
      lastActivity: "Not available",
    };

    render(<LeadsTable leads={[lead]} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByText("Test lead")).toHaveLength(2);
    expect(screen.getAllByText("New")).toHaveLength(2);
    expect(screen.getAllByText("Unavailable")).toHaveLength(2);
  });
});
