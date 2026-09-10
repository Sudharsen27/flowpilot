import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LeadsPage from "@/app/(app)/leads/page";
import { LeadStatusBadge } from "@/components/leads/lead-status-badge";
import { LeadsTable } from "@/components/leads/leads-table";
import { QualificationStatus } from "@/components/leads/qualification-status";
import { ApiError } from "@/lib/api/client";
import {
  approveLeadResponseDraft,
  createLead,
  generateLeadResponseDraft,
  getLeadResponseDraft,
  getLeads,
  qualifyLead,
  rejectLeadResponseDraft,
  sendLeadResponseDraft,
  updateLead,
  updateLeadResponseDraft,
  getLeadFollowUps,
} from "@/lib/api/leads";
import type { Lead, LeadEmailSendResult, LeadListResponse, LeadResponseDraftResult } from "@/types/api";

vi.mock("@/lib/api/leads", () => ({
  getLeads: vi.fn(),
  createLead: vi.fn(),
  updateLead: vi.fn(),
  qualifyLead: vi.fn(),
  generateLeadResponseDraft: vi.fn(),
  getLeadResponseDraft: vi.fn(),
  updateLeadResponseDraft: vi.fn(),
  approveLeadResponseDraft: vi.fn(),
  rejectLeadResponseDraft: vi.fn(),
  sendLeadResponseDraft: vi.fn(),
  getLeadFollowUps: vi.fn(),
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

function completedDraft(
  overrides: Partial<LeadResponseDraftResult> = {},
): LeadResponseDraftResult {
  return {
    id: "d-1",
    lead_id: "lead-1",
    status: "COMPLETED",
    enquiry: "We want a demo next week",
    original_response: "Thanks for reaching out. Could we schedule a demo?",
    response: "Thanks for reaching out. Could we schedule a demo?",
    human_edited: false,
    review_status: "GENERATED",
    reviewed_by_user_id: null,
    reviewed_at: null,
    rejection_reason: null,
    revision: 1,
    error: null,
    failure_category: null,
    provider: "fake",
    model: "fake-model",
    usage: { total_tokens: 30 },
    started_at: "2026-09-10T10:00:00Z",
    completed_at: "2026-09-10T10:00:01Z",
    created_at: "2026-09-10T10:00:00Z",
    updated_at: "2026-09-10T10:00:01Z",
    duration_ms: 1000,
    ...overrides,
  };
}

const getLeadsMock = vi.mocked(getLeads);
const createLeadMock = vi.mocked(createLead);
const updateLeadMock = vi.mocked(updateLead);
const qualifyLeadMock = vi.mocked(qualifyLead);
const generateLeadResponseDraftMock = vi.mocked(generateLeadResponseDraft);
const getLeadResponseDraftMock = vi.mocked(getLeadResponseDraft);
const updateLeadResponseDraftMock = vi.mocked(updateLeadResponseDraft);
const approveLeadResponseDraftMock = vi.mocked(approveLeadResponseDraft);
const rejectLeadResponseDraftMock = vi.mocked(rejectLeadResponseDraft);
const sendLeadResponseDraftMock = vi.mocked(sendLeadResponseDraft);
const getLeadFollowUpsMock = vi.mocked(getLeadFollowUps);

describe("Leads page", () => {
  beforeEach(() => {
    getLeadsMock.mockReset();
    createLeadMock.mockReset();
    updateLeadMock.mockReset();
    qualifyLeadMock.mockReset();
    generateLeadResponseDraftMock.mockReset();
    getLeadResponseDraftMock.mockReset();
    updateLeadResponseDraftMock.mockReset();
    approveLeadResponseDraftMock.mockReset();
    rejectLeadResponseDraftMock.mockReset();
    sendLeadResponseDraftMock.mockReset();
    getLeadFollowUpsMock.mockReset();
    getLeadFollowUpsMock.mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      total: 0,
    });
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
      "AI response drafts",
      "Follow-ups",
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
        name: "AI qualification is an analysis, not CRM status",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", {
        name: "Nothing has been sent",
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
    expect(screen.getAllByText("Not assessed").length).toBeGreaterThan(0);
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
    expect(screen.getAllByText("Not assessed")).toHaveLength(2);
  });

  it("analyzes a lead with AI and keeps CRM status distinct", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    qualifyLeadMock.mockResolvedValue({
      id: "q-1",
      lead_id: "lead-1",
      status: "COMPLETED",
      enquiry: "We want a demo next week",
      analysis: {
        summary: "The sender asked for a demo.",
        intent: "REQUEST_DEMO",
        qualification: "NEEDS_MORE_INFORMATION",
        qualification_reasons: ["Budget is not stated"],
        confidence: 0.61,
        extracted_contact: { name: null, email: null, phone: null },
        extracted_company: { name: null },
        buying_signals: ["Asked for a demo"],
        missing_information: ["Budget"],
      },
      error: null,
      failure_category: null,
      provider: "fake",
      model: "fake-model",
      usage: { total_tokens: 18 },
      started_at: "2026-09-10T10:00:00Z",
      completed_at: "2026-09-10T10:00:01Z",
      created_at: "2026-09-10T10:00:00Z",
      duration_ms: 1000,
    });
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Analyze with AI" })[0]);
    expect(
      screen.getByText(/does not change the lead's CRM status/i),
    ).toBeVisible();
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "We want a demo next week");
    await user.click(screen.getByRole("button", { name: "Analyze enquiry" }));
    expect(await screen.findByText("AI: Needs more information")).toBeVisible();
    expect(screen.getByText("Budget is not stated")).toBeVisible();
    expect(screen.getByText("Budget")).toBeVisible();
    expect(
      screen.getByText(/Self-reported model confidence \(not calibrated\): 0.61/),
    ).toBeVisible();
    expect(screen.getByText(/CRM status for Ada Prospect: NEW/)).toBeVisible();
    expect(qualifyLeadMock).toHaveBeenCalledWith("lead-1", {
      enquiry: "We want a demo next week",
    });
  });

  it("protects analyze from duplicate submits and can retry errors", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    let resolveQualify: (value: never) => void = () => undefined;
    qualifyLeadMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveQualify = resolve as (value: never) => void;
      }),
    );
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Analyze with AI" })[0]);
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "Need a demo");
    const submit = screen.getByRole("button", { name: "Analyze enquiry" });
    await user.click(submit);
    expect(screen.getByRole("button", { name: "Analyzing…" })).toBeDisabled();
    expect(qualifyLeadMock).toHaveBeenCalledTimes(1);
    resolveQualify(
      {
        id: "q-1",
        lead_id: "lead-1",
        status: "COMPLETED",
        enquiry: "Need a demo",
        analysis: {
          summary: "Demo request",
          intent: "REQUEST_DEMO",
          qualification: "QUALIFIED",
          qualification_reasons: [],
          confidence: 0.4,
          extracted_contact: { name: null, email: null, phone: null },
          extracted_company: { name: null },
          buying_signals: [],
          missing_information: [],
        },
        error: null,
        failure_category: null,
        provider: "fake",
        model: "fake-model",
        usage: null,
        started_at: "2026-09-10T10:00:00Z",
        completed_at: "2026-09-10T10:00:01Z",
        created_at: "2026-09-10T10:00:00Z",
        duration_ms: 10,
      } as never,
    );
  });

  it("shows provider unavailable errors from analyze", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    qualifyLeadMock.mockRejectedValue(
      new ApiError("Request failed: 503", 503, { detail: "not configured" }),
    );
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Analyze with AI" })[0]);
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "Need a demo");
    await user.click(screen.getByRole("button", { name: "Analyze enquiry" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "AI provider is not configured",
    );
    expect(screen.getByRole("button", { name: "Retry analysis" })).toBeVisible();
  });

  it("drafts a response without implying it was sent", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    generateLeadResponseDraftMock.mockResolvedValue(completedDraft());
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Draft response" })[0]);
    expect(screen.getAllByText(/Nothing has been sent/).length).toBeGreaterThan(
      0,
    );
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "We want a demo next week");
    await user.click(screen.getByRole("button", { name: "Generate draft" }));
    expect(
      await screen.findByText("Thanks for reaching out. Could we schedule a demo?"),
    ).toBeVisible();
    expect(screen.getByText("AI draft")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Copy draft" }));
    expect(writeText).toHaveBeenCalledWith(
      "Thanks for reaching out. Could we schedule a demo?",
    );
    expect(screen.getByText(/CRM status for Ada Prospect: NEW/)).toBeVisible();
    expect(generateLeadResponseDraftMock).toHaveBeenCalledWith("lead-1", {
      enquiry: "We want a demo next week",
    });
  });

  it("protects draft generation from duplicate submits and can retry errors", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    let resolveDraft: (value: never) => void = () => undefined;
    generateLeadResponseDraftMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveDraft = resolve as (value: never) => void;
      }),
    );
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Draft response" })[0]);
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "Need a demo");
    const submit = screen.getByRole("button", { name: "Generate draft" });
    await user.click(submit);
    expect(screen.getByRole("button", { name: "Generating…" })).toBeDisabled();
    expect(generateLeadResponseDraftMock).toHaveBeenCalledTimes(1);
    resolveDraft(
      completedDraft({
        enquiry: "Need a demo",
        original_response: "First draft",
        response: "First draft",
        usage: null,
        duration_ms: 10,
      }) as never,
    );
    expect(await screen.findByText("First draft")).toBeVisible();
  });

  it("retries a failed draft generation", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    generateLeadResponseDraftMock.mockRejectedValueOnce(
      new ApiError("Request failed: 502", 502, { detail: "AI provider request failed" }),
    );
    generateLeadResponseDraftMock.mockResolvedValueOnce(
      completedDraft({
        id: "d-2",
        enquiry: "Need a demo",
        original_response: "Happy to help with a demo.",
        response: "Happy to help with a demo.",
        usage: null,
        duration_ms: 10,
      }),
    );
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Draft response" })[0]);
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "Need a demo");
    await user.click(screen.getByRole("button", { name: "Generate draft" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "AI provider request failed",
    );
    expect(enquiry).toHaveValue("Need a demo");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Happy to help with a demo.")).toBeVisible();
    expect(generateLeadResponseDraftMock).toHaveBeenCalledTimes(2);
  });

  it("shows provider unavailable errors from draft response", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    generateLeadResponseDraftMock.mockRejectedValue(
      new ApiError("Request failed: 503", 503, { detail: "not configured" }),
    );
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Draft response" })[0]);
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "Need a demo");
    await user.click(screen.getByRole("button", { name: "Generate draft" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "AI provider is not configured",
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  it("edits, approves, and rejects a generated draft", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    generateLeadResponseDraftMock.mockResolvedValue(completedDraft());
    updateLeadResponseDraftMock.mockResolvedValue(
      completedDraft({
        response: "Edited reply",
        human_edited: true,
        review_status: "EDITED",
        revision: 2,
      }),
    );
    approveLeadResponseDraftMock.mockResolvedValue(
      completedDraft({
        response: "Edited reply",
        human_edited: true,
        review_status: "APPROVED",
        revision: 3,
        reviewed_by_user_id: "user-1",
        reviewed_at: "2026-09-10T10:02:00Z",
      }),
    );
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Draft response" })[0]);
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "We want a demo next week");
    await user.click(screen.getByRole("button", { name: "Generate draft" }));
    expect(await screen.findByText("Awaiting review")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const editor = screen.getByRole("textbox", { name: /^Edited response/ });
    await user.clear(editor);
    await user.type(editor, "Edited reply");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(updateLeadResponseDraftMock).toHaveBeenCalledWith("lead-1", "d-1", {
      response: "Edited reply",
      expected_revision: 1,
    });
    expect(await screen.findByText("Edited — needs review")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(screen.getByRole("heading", { name: "Approve this response?" })).toBeVisible();
    await user.click(screen.getAllByRole("button", { name: "Approve" }).at(-1)!);
    expect(approveLeadResponseDraftMock).toHaveBeenCalledWith("lead-1", "d-1", {
      expected_revision: 2,
    });
    expect(await screen.findByText("Approved (not sent)")).toBeVisible();
    expect(screen.getByRole("button", { name: "Send email" })).toBeVisible();
  });

  it("cancels an edit and can reject with a reason", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    generateLeadResponseDraftMock.mockResolvedValue(completedDraft());
    rejectLeadResponseDraftMock.mockResolvedValue(
      completedDraft({
        review_status: "REJECTED",
        rejection_reason: "Too vague",
        revision: 2,
        reviewed_by_user_id: "user-1",
        reviewed_at: "2026-09-10T10:03:00Z",
      }),
    );
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Draft response" })[0]);
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "We want a demo next week");
    await user.click(screen.getByRole("button", { name: "Generate draft" }));
    await screen.findByText("AI draft");
    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("textbox", { name: /^Edited response/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reject" }));
    await user.type(
      screen.getByRole("textbox", { name: /^Rejection reason/ }),
      "Too vague",
    );
    await user.click(screen.getByRole("button", { name: "Confirm reject" }));
    expect(rejectLeadResponseDraftMock).toHaveBeenCalledWith("lead-1", "d-1", {
      expected_revision: 1,
      reason: "Too vague",
    });
    expect(await screen.findByText("Rejected")).toBeVisible();
    expect(screen.getByText("Rejection reason: Too vague")).toBeVisible();
  });

  it("shows stale draft conflicts from approve", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    generateLeadResponseDraftMock.mockResolvedValue(completedDraft());
    approveLeadResponseDraftMock.mockRejectedValue(
      new ApiError("Request failed: 409", 409, { detail: "changed" }),
    );
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Draft response" })[0]);
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "We want a demo next week");
    await user.click(screen.getByRole("button", { name: "Generate draft" }));
    await screen.findByRole("button", { name: "Approve" });
    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.click(screen.getAllByRole("button", { name: "Approve" }).at(-1)!);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This draft changed. Refresh and review the latest version.",
    );
  });

  it("maps review API errors for 403 and 404", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(
      listResponse([
        {
          ...lead,
          latest_response_draft: {
            id: "d-1",
            status: "COMPLETED",
            review_status: "GENERATED",
            created_at: "2026-09-10T10:00:00Z",
          },
        },
      ]),
    );
    getLeadResponseDraftMock.mockRejectedValueOnce(
      new ApiError("Request failed: 403", 403, { detail: "forbidden" }),
    );
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Review draft" })[0]);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You do not have permission to review this draft.",
    );
  });

  it("maps a missing draft to a 404 message", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(
      listResponse([
        {
          ...lead,
          latest_response_draft: {
            id: "d-1",
            status: "COMPLETED",
            review_status: "GENERATED",
            created_at: "2026-09-10T10:00:00Z",
          },
        },
      ]),
    );
    getLeadResponseDraftMock.mockRejectedValue(
      new ApiError("Request failed: 404", 404, { detail: "missing" }),
    );
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Review draft" })[0]);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This draft could not be found.",
    );
  });

  function approvedDraft() {
    return completedDraft({
      review_status: "APPROVED",
      reviewed_by_user_id: "user-1",
      reviewed_at: "2026-09-10T10:04:00Z",
    });
  }

  function emailSend(overrides: Partial<LeadEmailSendResult> = {}): LeadEmailSendResult {
    return {
      id: "s-1",
      lead_id: "lead-1",
      response_draft_id: "d-1",
      status: "SENT",
      recipient_email: "ada@example.com",
      sender_email: "noreply@example.com",
      subject: "Re: Your enquiry",
      body_text: "Thanks for reaching out. Could we schedule a demo?",
      draft_revision: 1,
      provider: "fake-email",
      provider_message_id: "msg_1",
      error: null,
      failure_category: null,
      started_at: "2026-09-10T10:05:00Z",
      completed_at: "2026-09-10T10:05:01Z",
      created_at: "2026-09-10T10:05:00Z",
      duration_ms: 1000,
      ...overrides,
    };
  }

  async function openApproved(user: ReturnType<typeof userEvent.setup>) {
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    generateLeadResponseDraftMock.mockResolvedValue(approvedDraft());
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Draft response" })[0]);
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "We want a demo next week");
    await user.click(screen.getByRole("button", { name: "Generate draft" }));
    expect(await screen.findByRole("button", { name: "Send email" })).toBeVisible();
  }

  it("does not show send for generated drafts", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    generateLeadResponseDraftMock.mockResolvedValue(completedDraft());
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Draft response" })[0]);
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "We want a demo next week");
    await user.click(screen.getByRole("button", { name: "Generate draft" }));
    await screen.findByText("Awaiting review");
    expect(screen.queryByRole("button", { name: "Send email" })).not.toBeInTheDocument();
  });

  it("confirms and sends an approved email", async () => {
    const user = userEvent.setup();
    sendLeadResponseDraftMock.mockResolvedValue(emailSend());
    await openApproved(user);
    await user.click(screen.getByRole("button", { name: "Send email" }));
    const sendHeading = screen.getByRole("heading", { name: "Send this email?" });
    expect(sendHeading).toBeVisible();
    const sendDialog = sendHeading.closest("[data-slot='dialog-content']") ?? sendHeading.parentElement;
    expect(sendDialog).not.toBeNull();
    expect(within(sendDialog as HTMLElement).getByText("ada@example.com")).toBeVisible();
    expect(within(sendDialog as HTMLElement).getByText("Re: Your enquiry")).toBeVisible();
    expect(
      screen.getByText("This will send the approved response to the lead. This is an external action."),
    ).toBeVisible();
    await user.click(screen.getAllByRole("button", { name: "Send email" }).at(-1)!);
    expect(sendLeadResponseDraftMock).toHaveBeenCalledWith("lead-1", "d-1");
    expect(sendLeadResponseDraftMock).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("SENT")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Send email" })).not.toBeInTheDocument();
  });

  it("disables send while the request is in flight", async () => {
    const user = userEvent.setup();
    let resolveSend: (value: ReturnType<typeof emailSend>) => void = () => undefined;
    sendLeadResponseDraftMock.mockReturnValue(
      new Promise((resolve) => {
        resolveSend = resolve;
      }),
    );
    await openApproved(user);
    await user.click(screen.getByRole("button", { name: "Send email" }));
    await user.click(screen.getAllByRole("button", { name: "Send email" }).at(-1)!);
    expect(screen.getAllByRole("button", { name: "Sending…" }).length).toBeGreaterThan(0);
    resolveSend(emailSend());
    expect(await screen.findByText("SENT")).toBeVisible();
  });

  it("maps send failures without inventing a sent state", async () => {
    const user = userEvent.setup();
    sendLeadResponseDraftMock.mockRejectedValueOnce(
      new ApiError("Request failed: 503", 503, { detail: "Email provider is not configured" }),
    );
    sendLeadResponseDraftMock.mockRejectedValueOnce(
      new ApiError("Request failed: 502", 502, emailSend({ status: "FAILED", error: "fail", failure_category: "PROVIDER_ERROR" })),
    );
    sendLeadResponseDraftMock.mockRejectedValueOnce(
      new ApiError("Request failed: 409", 409, { detail: "This draft is not approved for sending." }),
    );
    sendLeadResponseDraftMock.mockRejectedValueOnce(
      new ApiError("Request failed: 409", 409, {
        ...emailSend(),
        detail: "This email was already sent.",
      } as LeadEmailSendResult),
    );
    sendLeadResponseDraftMock.mockRejectedValueOnce(
      new ApiError("Request failed: 422", 422, { detail: "This lead has no email address." }),
    );
    await openApproved(user);
    await user.click(screen.getByRole("button", { name: "Send email" }));
    await user.click(screen.getAllByRole("button", { name: "Send email" }).at(-1)!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Email provider is not configured");
    expect(screen.queryByText("SENT")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Send email" }));
    await user.click(screen.getAllByRole("button", { name: "Send email" }).at(-1)!);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The email provider could not send this message.",
    );
    expect(screen.getByText("Approved (not sent)")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Send email" }));
    await user.click(screen.getAllByRole("button", { name: "Send email" }).at(-1)!);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This draft is not approved for sending.",
    );
    await user.click(screen.getByRole("button", { name: "Send email" }));
    await user.click(screen.getAllByRole("button", { name: "Send email" }).at(-1)!);
    expect(await screen.findByText("SENT")).toBeVisible();
    expect(await screen.findByRole("alert")).toHaveTextContent("This email was already sent.");
  });

  it("does not offer send when the lead has no email", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([{ ...lead, email: null }]));
    generateLeadResponseDraftMock.mockResolvedValue(approvedDraft());
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Draft response" })[0]);
    const enquiry = screen.getByRole("textbox", { name: /^Customer enquiry/ });
    await user.clear(enquiry);
    await user.type(enquiry, "We want a demo next week");
    await user.click(screen.getByRole("button", { name: "Generate draft" }));
    await screen.findByText("Approved (not sent)");
    expect(screen.queryByRole("button", { name: "Send email" })).not.toBeInTheDocument();
  });

  it("opens follow-ups for a lead", async () => {
    const user = userEvent.setup();
    getLeadsMock.mockResolvedValue(listResponse([lead]));
    render(<LeadsPage />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Follow-ups" })[0]);
    expect(await screen.findByText("No follow-ups yet.")).toBeVisible();
    expect(getLeadFollowUpsMock).toHaveBeenCalledWith("lead-1");
  });
});

