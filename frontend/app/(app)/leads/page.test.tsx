import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LeadsPage from "@/app/(app)/leads/page";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { LeadsTable } from "@/components/leads/leads-table";
import { QualificationStatus } from "@/components/leads/qualification-status";
import { ApiError } from "@/lib/api/client";
import { createLead, getLeads, updateLead } from "@/lib/api/leads";
import type { Lead, LeadListResponse } from "@/types/api";

vi.mock("@/lib/api/leads", () => ({
  getLeads: vi.fn(),
  createLead: vi.fn(),
  updateLead: vi.fn(),
}));

const lead: Lead = {
  id: "lead-1",
  name: "Ada Prospect",
  email: "ada@example.com",
  phone: "555-0100",
  company: "Acme",
  source: "WEBSITE",
  status: "NEW",
  notes: "Inbound form",
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-10T10:00:00Z",
};

function listResponse(
  items: Lead[],
  overrides: Partial<LeadListResponse> = {},
): LeadListResponse {
  return {
    items,
    limit: 20,
    offset: 0,
    total: items.length,
    status_counts: {
      NEW: items.filter((item) => item.status === "NEW").length,
      CONTACTED: items.filter((item) => item.status === "CONTACTED").length,
      QUALIFIED: items.filter((item) => item.status === "QUALIFIED").length,
      UNQUALIFIED: items.filter((item) => item.status === "UNQUALIFIED").length,
      CONVERTED: items.filter((item) => item.status === "CONVERTED").length,
    },
    ...overrides,
  };
}

const getLeadsMock = vi.mocked(getLeads);
const createLeadMock = vi.mocked(createLead);
const updateLeadMock = vi.mocked(updateLead);

describe("Leads page", () => {
  beforeEach(() => {
    getLeadsMock.mockReset();
    createLeadMock.mockReset();
    updateLeadMock.mockReset();
  });

  it("renders the page hierarchy and loading state", () => {
    getLeadsMock.mockReturnValue(new Promise(() => undefined));
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
    expect(screen.getByText("Loading records")).toBeInTheDocument();
    expect(screen.queryByText("Example")).not.toBeInTheDocument();
  });

  it("shows an empty directory without fabricated lead rows", async () => {
    getLeadsMock.mockResolvedValue(listResponse([]));
    render(<LeadsPage />);

    expect(
      await screen.findByRole("heading", { name: "No leads yet" }),
    ).toBeVisible();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("Example")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "AI qualification is not connected",
      }),
    ).toBeVisible();
    const cards = screen.getAllByRole("article");
    expect(within(cards[0]).getByText("0")).toBeVisible();
    expect(within(cards[3]).getByText("—")).toBeVisible();
  });

  it("renders real API leads in the directory", async () => {
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    render(<LeadsPage />);

    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.getAllByText("Ada Prospect").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ada@example.com").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Acme").length).toBeGreaterThan(0);
    expect(screen.getAllByText("New").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Website").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.getByText("Showing 1–1 of 1")).toBeVisible();
  });

  it("shows an API error and retries", async () => {
    const user = userEvent.setup();
    getLeadsMock
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(listResponse([lead]));
    render(<LeadsPage />);
    expect(
      await screen.findByRole("heading", { name: "Leads could not be loaded" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect((await screen.findAllByText("Ada Prospect")).length).toBeGreaterThan(
      0,
    );
    expect(getLeadsMock).toHaveBeenCalledTimes(2);
  });

  it("sends search and filters to the API and can clear them", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    render(<LeadsPage />);
    await screen.findByRole("table");

    await user.type(screen.getByRole("searchbox", { name: "Search leads" }), "Ada");
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Lead status" }),
      "NEW",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Lead source" }),
      "WEBSITE",
    );

    await waitFor(() =>
      expect(getLeadsMock).toHaveBeenLastCalledWith({
        q: "Ada",
        status: "NEW",
        source: "WEBSITE",
        limit: 20,
        offset: 0,
      }),
    );

    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    await waitFor(() =>
      expect(getLeadsMock).toHaveBeenLastCalledWith({
        q: undefined,
        status: undefined,
        source: undefined,
        limit: 20,
        offset: 0,
      }),
    );
  });

  it("paginates with previous and next", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(
      listResponse([lead], { total: 21, offset: 0 }),
    );
    render(<LeadsPage />);
    expect(await screen.findByText("Showing 1–20 of 21")).toBeVisible();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(getLeadsMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 20, limit: 20 }),
      ),
    );
  });

  it("creates a lead and refreshes the directory", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([]));
    createLeadMock.mockResolvedValue({ ...lead, id: "lead-new" });
    render(<LeadsPage />);
    await screen.findByRole("heading", { name: "No leads yet" });
    await user.click(screen.getByRole("button", { name: "Create lead" }));
    await user.type(screen.getByRole("textbox", { name: /^Name/ }), "New lead");
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Create lead",
      }),
    );
    await waitFor(() =>
      expect(createLeadMock).toHaveBeenCalledWith({
        name: "New lead",
        email: null,
        phone: null,
        company: null,
        source: "MANUAL",
        status: "NEW",
        notes: null,
      }),
    );
    expect(getLeadsMock.mock.calls.length).toBeGreaterThan(1);
  });

  it("prevents duplicate create submissions", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([]));
    let resolveCreate: (value: Lead) => void = () => undefined;
    createLeadMock.mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve;
      }),
    );
    render(<LeadsPage />);
    await screen.findByRole("heading", { name: "No leads yet" });
    await user.click(screen.getByRole("button", { name: "Create lead" }));
    await user.type(screen.getByRole("textbox", { name: /^Name/ }), "New lead");
    const submit = within(screen.getByRole("dialog")).getByRole("button", {
      name: "Create lead",
    });
    await user.click(submit);
    expect(createLeadMock).toHaveBeenCalledTimes(1);
    expect(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Saving…",
      }),
    ).toBeDisabled();
    resolveCreate({ ...lead, id: "lead-new" });
  });

  it("keeps create disabled until a name is provided", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([]));
    render(<LeadsPage />);
    await screen.findByRole("heading", { name: "No leads yet" });
    await user.click(screen.getByRole("button", { name: "Create lead" }));
    expect(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Create lead",
      }),
    ).toBeDisabled();
  });

  it("shows create API errors", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([]));
    createLeadMock.mockRejectedValue(
      new ApiError("Request failed: 422", 422, { detail: "invalid" }),
    );
    render(<LeadsPage />);
    await screen.findByRole("heading", { name: "No leads yet" });
    await user.click(screen.getByRole("button", { name: "Create lead" }));
    await user.type(screen.getByRole("textbox", { name: /^Name/ }), "New lead");
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Create lead",
      }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Review the lead details",
    );
  });

  it("edits a lead through the API", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    updateLeadMock.mockResolvedValue({ ...lead, status: "CONTACTED" });
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Edit" })[0]);
    expect(screen.getByRole("heading", { name: "Edit lead" })).toBeVisible();
    await user.selectOptions(
      screen.getByRole("combobox", { name: /^Status/ }),
      "CONTACTED",
    );
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() =>
      expect(updateLeadMock).toHaveBeenCalledWith(
        "lead-1",
        expect.objectContaining({ status: "CONTACTED", name: "Ada Prospect" }),
      ),
    );
  });

  it("maps typed lead and qualification states to visible text", () => {
    render(
      <>
        <LeadStatusBadge status="CONTACTED" />
        <QualificationStatus status="not-assessed" />
      </>,
    );

    expect(screen.getByText("Contacted")).toBeVisible();
    expect(screen.getByText("Not assessed")).toBeVisible();
    expect(screen.queryByText(/\/100/)).not.toBeInTheDocument();
  });

  it("supports desktop table and mobile list representations for real rows", () => {
    render(<LeadsTable leads={[lead]} />);

    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getAllByText("Ada Prospect")).toHaveLength(2);
    expect(screen.getAllByText("New")).toHaveLength(2);
    expect(screen.getAllByText("Unavailable")).toHaveLength(2);
  });
});
