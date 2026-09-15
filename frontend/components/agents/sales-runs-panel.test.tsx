import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SalesRunsPanel } from "@/components/agents/sales-runs-panel";
import { ApiError } from "@/lib/api/client";
import { getLead, getLeadResponseDraft } from "@/lib/api/leads";
import { cancelSalesRun, listSalesRuns, sendSalesRun, startSalesRun } from "@/lib/api/sales-runs";
import type { Lead, SalesRun } from "@/types/api";

vi.mock("@/lib/api/sales-runs", () => ({
  listSalesRuns: vi.fn(),
  startSalesRun: vi.fn(),
  cancelSalesRun: vi.fn(),
  sendSalesRun: vi.fn(),
  getSalesRun: vi.fn(),
}));

vi.mock("@/lib/api/leads", () => ({
  getLead: vi.fn(),
  getLeadResponseDraft: vi.fn(),
  generateLeadResponseDraft: vi.fn(),
  updateLeadResponseDraft: vi.fn(),
  approveLeadResponseDraft: vi.fn(),
  rejectLeadResponseDraft: vi.fn(),
  sendLeadResponseDraft: vi.fn(),
}));

const listSalesRunsMock = vi.mocked(listSalesRuns);
const startSalesRunMock = vi.mocked(startSalesRun);
const cancelSalesRunMock = vi.mocked(cancelSalesRun);
const sendSalesRunMock = vi.mocked(sendSalesRun);
const getLeadMock = vi.mocked(getLead);
const getLeadResponseDraftMock = vi.mocked(getLeadResponseDraft);

const lead: Lead = {
  id: "lead-1",
  name: "Ada Prospect",
  email: "ada@example.com",
  phone: null,
  company: null,
  source: "API",
  status: "NEW",
  notes: null,
  created_at: "2026-09-11T10:00:00Z",
  updated_at: "2026-09-11T10:00:00Z",
};

function run(overrides: Partial<SalesRun> = {}): SalesRun {
  return {
    id: "run-1",
    agent_id: "agent-1",
    lead_id: "lead-1",
    status: "WAITING_APPROVAL",
    stage: "AWAIT_APPROVAL",
    qualification_id: "q-1",
    response_draft_id: "draft-1",
    email_send_id: null,
    failure_category: null,
    error: null,
    initiated_by_user_id: "user-1",
    revision: 2,
    started_at: "2026-09-11T10:00:00Z",
    completed_at: null,
    created_at: "2026-09-11T10:00:00Z",
    updated_at: "2026-09-11T10:00:01Z",
    lead: {
      id: "lead-1",
      name: "Ada Prospect",
      email: "ada@example.com",
      status: "NEW",
    },
    ...overrides,
  };
}

function page(items: SalesRun[]) {
  return { items, limit: 20, offset: 0, total: items.length };
}

describe("SalesRunsPanel", () => {
  beforeEach(() => {
    listSalesRunsMock.mockReset();
    startSalesRunMock.mockReset();
    cancelSalesRunMock.mockReset();
    sendSalesRunMock.mockReset();
    getLeadMock.mockReset();
    getLeadResponseDraftMock.mockReset();
    getLeadResponseDraftMock.mockResolvedValue({
      id: "draft-1",
      lead_id: "lead-1",
      status: "COMPLETED",
      enquiry: "Need a demo",
      original_response: "Thanks",
      response: "Thanks",
      human_edited: false,
      review_status: "GENERATED",
      reviewed_by_user_id: null,
      reviewed_at: null,
      rejection_reason: null,
      revision: 1,
      error: null,
      failure_category: null,
      provider: "fake",
      model: "fake",
      usage: null,
      started_at: "2026-09-11T10:00:00Z",
      completed_at: "2026-09-11T10:00:01Z",
      created_at: "2026-09-11T10:00:00Z",
      updated_at: "2026-09-11T10:00:01Z",
      duration_ms: 1000,
      latest_email_send: null,
    });
    listSalesRunsMock.mockResolvedValue(page([]));
  });

  it("shows loading state", () => {
    listSalesRunsMock.mockReturnValue(new Promise(() => undefined));
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    expect(screen.getByRole("heading", { name: "Sales runs" })).toBeVisible();
  });

  it("shows empty state", async () => {
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    expect(await screen.findByText("No sales runs yet")).toBeVisible();
  });

  it("shows error state and retry", async () => {
    const user = userEvent.setup();
    listSalesRunsMock
      .mockRejectedValueOnce(new ApiError("failed", 500))
      .mockResolvedValueOnce(page([]));
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    expect(
      await screen.findByRole("heading", { name: "Sales runs could not be loaded" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No sales runs yet")).toBeVisible();
  });

  it("renders run states and opens the existing draft dialog", async () => {
    const user = userEvent.setup();
    listSalesRunsMock.mockResolvedValue(
      page([
        run({ id: "run-wait", status: "WAITING_APPROVAL" }),
        run({
          id: "run-running",
          status: "RUNNING",
          stage: "QUALIFY",
          response_draft_id: null,
        }),
        run({
          id: "run-failed",
          status: "FAILED",
          stage: "QUALIFY",
          error: "AI provider request failed",
          response_draft_id: null,
        }),
        run({ id: "run-cancelled", status: "CANCELLED", response_draft_id: null }),
      ]),
    );
    getLeadMock.mockResolvedValue(lead);
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    expect((await screen.findAllByText("Ada Prospect")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Waiting for approval").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Processing").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Failed").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Cancelled").length).toBeGreaterThan(0);
    expect(screen.getAllByText("AI provider request failed").length).toBeGreaterThan(0);
    await user.click(screen.getAllByRole("button", { name: "Review draft" })[0]!);
    expect(getLeadMock).toHaveBeenCalledWith("lead-1");
    expect(await screen.findByText("Draft response")).toBeVisible();
    expect(screen.queryByText("Draft editor copy")).not.toBeInTheDocument();
  });

  it("starts a sales run after validating enquiry and name", async () => {
    const user = userEvent.setup();
    listSalesRunsMock
      .mockResolvedValueOnce(page([]))
      .mockResolvedValueOnce(page([run()]));
    startSalesRunMock.mockResolvedValue(run());
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    await user.click(await screen.findByRole("button", { name: "Start sales run" }));
    expect(screen.getByRole("heading", { name: "Start Sales Run" })).toBeVisible();
    const submit = () =>
      screen.getAllByRole("button", { name: "Start sales run" }).at(-1)!;
    await user.click(submit());
    expect(screen.getByText("Enquiry is required.")).toBeVisible();
    await user.type(screen.getByLabelText(/Enquiry/), "Need a demo next week");
    await user.click(submit());
    expect(screen.getByText("Name is required to create a lead.")).toBeVisible();
    await user.type(screen.getByLabelText(/^Name/), "Ada Prospect");
    await user.click(submit());
    await waitFor(() => expect(startSalesRunMock).toHaveBeenCalledTimes(1));
    expect(startSalesRunMock).toHaveBeenCalledWith("agent-1", {
      enquiry: "Need a demo next week",
      lead_id: undefined,
      email: undefined,
      name: "Ada Prospect",
    });
    expect(await screen.findAllByText("Waiting for approval")).not.toHaveLength(0);
  });

  it("prevents duplicate start submission and shows API errors", async () => {
    const user = userEvent.setup();
    let resolve: (value: SalesRun) => void = () => undefined;
    startSalesRunMock.mockImplementation(
      () =>
        new Promise<SalesRun>((next) => {
          resolve = next;
        }),
    );
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    await user.click(await screen.findByRole("button", { name: "Start sales run" }));
    await user.type(screen.getByLabelText(/Enquiry/), "Need a demo");
    await user.type(screen.getByLabelText(/^Name/), "Ada");
    await user.click(screen.getAllByRole("button", { name: "Start sales run" }).at(-1)!);
    expect(screen.getByRole("button", { name: "Starting…" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Starting…" }));
    expect(startSalesRunMock).toHaveBeenCalledTimes(1);
    resolve(run({ status: "FAILED", error: "AI provider request failed" }));
    await waitFor(() => expect(listSalesRunsMock).toHaveBeenCalledTimes(2));
  });

  it("shows start API errors without closing", async () => {
    const user = userEvent.setup();
    startSalesRunMock.mockRejectedValue(new ApiError("conflict", 409, { detail: "This lead already has an open sales run." }));
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    await user.click(await screen.findByRole("button", { name: "Start sales run" }));
    await user.type(screen.getByLabelText(/Enquiry/), "Need a demo");
    await user.type(screen.getByLabelText(/^Name/), "Ada");
    await user.click(screen.getAllByRole("button", { name: "Start sales run" }).at(-1)!);
    expect(
      await screen.findByText("This lead already has an open sales run."),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Start Sales Run" })).toBeVisible();
  });

  it("cancels through ConfirmDialog and refreshes", async () => {
    const user = userEvent.setup();
    listSalesRunsMock
      .mockResolvedValueOnce(page([run()]))
      .mockResolvedValueOnce(page([run({ status: "CANCELLED" })]));
    cancelSalesRunMock.mockResolvedValue(run({ status: "CANCELLED" }));
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    await user.click((await screen.findAllByRole("button", { name: "Cancel run" }))[0]!);
    const confirmTitle = await screen.findByRole("heading", { name: "Cancel sales run" });
    const dialog = confirmTitle.closest("[data-slot=dialog-content]");
    expect(dialog).toBeTruthy();
    await user.click(within(dialog as HTMLElement).getByRole("button", { name: "Cancel run" }));
    await waitFor(() =>
      expect(cancelSalesRunMock).toHaveBeenCalledWith("agent-1", "run-1", {
        expected_revision: 2,
      }),
    );
    expect(await screen.findAllByText("Cancelled")).not.toHaveLength(0);
  });

  it("hides Send until the nested draft is APPROVED", async () => {
    listSalesRunsMock.mockResolvedValue(
      page([
        run({
          response_draft: { id: "draft-1", status: "COMPLETED", review_status: "GENERATED" },
        }),
      ]),
    );
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    expect((await screen.findAllByRole("button", { name: "Review draft" })).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Send approved response" })).not.toBeInTheDocument();
  });

  it("sends only after confirmation and does not mark completed until refresh", async () => {
    const user = userEvent.setup();
    const approved = run({
      response_draft: { id: "draft-1", status: "COMPLETED", review_status: "APPROVED" },
    });
    listSalesRunsMock
      .mockResolvedValueOnce(page([approved]))
      .mockResolvedValueOnce(
        page([
          run({
            status: "COMPLETED",
            stage: "DONE",
            email_send_id: "send-1",
            completed_at: "2026-09-15T10:00:00Z",
            email_send: {
              id: "send-1",
              status: "SENT",
              recipient_email: "ada@example.com",
              provider: "fake-email",
              provider_message_id: "msg_1",
              draft_revision: 2,
              failure_category: null,
              error: null,
              started_at: "2026-09-15T10:00:00Z",
              completed_at: "2026-09-15T10:00:01Z",
              created_at: "2026-09-15T10:00:00Z",
            },
          }),
        ]),
      );
    let resolveSend: (value: SalesRun) => void = () => undefined;
    sendSalesRunMock.mockImplementation(
      () =>
        new Promise<SalesRun>((next) => {
          resolveSend = next;
        }),
    );
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    await user.click((await screen.findAllByRole("button", { name: "Send approved response" }))[0]!);
    expect(sendSalesRunMock).not.toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: "Send approved response?" })).toBeVisible();
    expect(screen.getAllByText(/Approval does not send the email/).length).toBeGreaterThan(0);
    expect(screen.getByText("ada@example.com")).toBeVisible();
    expect(screen.getByText("Re: Your enquiry")).toBeVisible();
    expect(screen.getByText("Thanks")).toBeVisible();
    const dialog = screen.getByRole("heading", { name: "Send approved response?" }).closest(
      "[data-slot=dialog-content]",
    ) as HTMLElement;
    await user.click(within(dialog).getByRole("button", { name: "Send approved response" }));
    expect(await screen.findByRole("button", { name: "Sending…" })).toBeDisabled();
    expect(screen.queryAllByText("Completed")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Sending…" }));
    expect(sendSalesRunMock).toHaveBeenCalledTimes(1);
    expect(sendSalesRunMock).toHaveBeenCalledWith("agent-1", "run-1", {
      expected_revision: 2,
    });
    resolveSend(
      run({
        status: "COMPLETED",
        stage: "DONE",
        email_send_id: "send-1",
      }),
    );
    expect((await screen.findAllByText("Completed")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Email sent/).length).toBeGreaterThan(0);
  });

  it("shows send failures and retry for a failed send run", async () => {
    const user = userEvent.setup();
    const failedSend = run({
      status: "FAILED",
      stage: "SEND",
      error: "Email provider request failed",
      response_draft: { id: "draft-1", status: "COMPLETED", review_status: "APPROVED" },
    });
    listSalesRunsMock
      .mockResolvedValueOnce(page([failedSend]))
      .mockResolvedValueOnce(page([failedSend]));
    sendSalesRunMock.mockRejectedValue(
      new ApiError("conflict", 409, { detail: "This draft is not approved for sending." }),
    );
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    expect((await screen.findAllByText("Failed")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Email provider request failed").length).toBeGreaterThan(0);
    await user.click(screen.getAllByRole("button", { name: "Send approved response" })[0]!);
    const dialog = (await screen.findByRole("heading", { name: "Send approved response?" })).closest(
      "[data-slot=dialog-content]",
    ) as HTMLElement;
    await user.click(within(dialog).getByRole("button", { name: "Send approved response" }));
    expect(
      await screen.findByText("This draft is not approved for sending."),
    ).toBeVisible();
    expect(screen.queryAllByText("Completed")).toHaveLength(0);
  });

  it("hides Send after an approved draft is edited", async () => {
    listSalesRunsMock.mockResolvedValue(
      page([
        run({
          response_draft: { id: "draft-1", status: "COMPLETED", review_status: "EDITED" },
        }),
      ]),
    );
    render(<SalesRunsPanel agentId="agent-1" canStart />);
    expect((await screen.findAllByRole("button", { name: "Review draft" })).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Send approved response" })).not.toBeInTheDocument();
  });
});
