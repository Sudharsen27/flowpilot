import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-display/data-table";
import { MetricCard } from "@/components/data-display/metric-card";
import { SearchInput } from "@/components/forms/search-input";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";

describe("design system foundations", () => {
  it("renders a reusable page header with breadcrumbs and actions", () => {
    render(
      <PageHeader
        title="Workspace"
        description="Manage workspace details."
        breadcrumbs={[
          { label: "Settings", href: "/settings" },
          { label: "Workspace" },
        ]}
        primaryAction={<Button>Save changes</Button>}
      />,
    );

    expect(screen.getByRole("heading", { name: "Workspace" })).toBeVisible();
    expect(screen.getByText("Manage workspace details.")).toBeVisible();
    expect(
      screen.getByRole("navigation", { name: "Breadcrumb" }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeVisible();
  });

  it("shows a truthful unavailable metric instead of inventing a value", () => {
    render(<MetricCard label="Leads handled" />);

    expect(screen.getByText("Leads handled")).toBeVisible();
    expect(screen.getByText("—")).toBeVisible();
    expect(screen.getByText("No data yet")).toBeVisible();
  });

  it("renders semantic status text and status metadata", () => {
    render(
      <>
        <StatusBadge status="active" />
        <StatusBadge status="failed" />
      </>,
    );

    expect(screen.getByText("Active")).toHaveAttribute("data-status", "active");
    expect(screen.getByText("Failed")).toHaveAttribute("data-status", "failed");
  });

  it("provides an accessible search control and clear action", async () => {
    const onClear = vi.fn();
    const user = userEvent.setup();
    render(
      <SearchInput
        label="Search records"
        value="Acme"
        onChange={() => undefined}
        onClear={onClear}
      />,
    );

    expect(
      screen.getByRole("searchbox", { name: "Search records" }),
    ).toHaveValue("Acme");
    await user.click(screen.getByRole("button", { name: "Clear search" }));
    expect(onClear).toHaveBeenCalledOnce();
  });

  it("renders a mobile list and desktop table from the same records", () => {
    type Record = { id: string; name: string };
    const columns: DataTableColumn<Record>[] = [
      { key: "name", header: "Name", cell: (row) => row.name },
    ];

    render(
      <DataTable
        columns={columns}
        rows={[{ id: "one", name: "First record" }]}
        getRowKey={(row) => row.id}
      />,
    );

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getAllByText("First record")).toHaveLength(2);
    expect(screen.getByRole("list")).toBeInTheDocument();
  });
});
