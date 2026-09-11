import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FollowUpOperations } from "@/components/leads/follow-up-operations";
import { ApiError } from "@/lib/api/client";
import {
  completeLeadFollowUp,
  getFollowUpOperations,
  getLead,
  getLeadFollowUpExecutions,
  getLeadFollowUps,
} from "@/lib/api/leads";
import type {
  FollowUpOperationsItem,
  FollowUpOperationsResponse,
  Lead,
  LeadFollowUp,
  LeadFollowUpExecution,
} from "@/types/api";

vi.mock("@/lib/api/leads", () => ({
  getFollowUpOperations: vi.fn(),
  getLead: vi.fn(),
  getLeadFollowUpExecutions: vi.fn(),
  getLeadFollowUps: vi.fn(),
  createLeadFollowUp: vi.fn(),
  updateLeadFollowUp: vi.fn(),
  completeLeadFollowUp: vi.fn(),
  cancelLeadFollowUp: vi.fn(),
}));

const getFollowUpOperationsMock = vi.mocked(getFollowUpOperations);
const getLeadMock = vi.mocked(getLead);
const getLeadFollowUpExecutionsMock = vi.mocked(getLeadFollowUpExecutions);
const getLeadFollowUpsMock = vi.mocked(getLeadFollowUps);
const completeLeadFollowUpMock = vi.mocked(completeLeadFollowUp);

const lead: Lead = {
  id: "lead-1",
  name: "Ada Prospect",
  email: "ada@example.com",
  phone: null,
  company: "Acme",
  source: "WEBSITE",
  status: "NEW",
  notes: null,
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-10T10:00:00Z",
};

function followUp(overrides: Partial<LeadFollowUp> = {}): LeadFollowUp {
  return {
    id: "fu-1",
    lead_id: "lead-1",
    email_send_id: null,
    type: "EMAIL_FOLLOW_UP",
    status: "PENDING",
    due_at: "2026-09-01T10:00:00Z",
    notes: "Check reply",
    body_text: "Checking in on your enquiry.",
    revision: 1,
    is_overdue: true,
    completed_at: null,
    cancelled_at: null,
    created_at: "2026-09-01T09:00:00Z",
    updated_at: "2026-09-01T09:00:00Z",
    ...overrides,
  };
}

function item(
  overrides: Partial<FollowUpOperationsItem> = {},
): FollowUpOperationsItem {
  return {
    follow_up: followUp(),
    lead: { id: "lead-1", name: "Ada Prospect", email: "ada@example.com" },
    latest_execution: null,
    ...overrides,
  };
}

function page(
  items: FollowUpOperationsItem[],
  overrides: Partial<FollowUpOperationsResponse> = {},
): FollowUpOperationsResponse {
  return {
    items,
    summary: {
      overdue: items.filter((row) => row.follow_up.is_overdue).length,
      due_today: 0,
      upcoming: 0,
      completed: items.filter((row) => row.follow_up.status === "COMPLETED")
        .length,
      cancelled: items.filter((row) => row.follow_up.status === "CANCELLED")
        .length,
    },
    limit: 20,
    offset: 0,
    total: items.length,
    ...overrides,
  };
}

function sentExecution(
  overrides: Partial<LeadFollowUpExecution> = {},
): LeadFollowUpExecution {
  return {
    id: "ex-1",
    lead_id: "lead-1",
    follow_up_id: "fu-1",
    status: "SENT",
    attempt: 1,
    recipient_email: "ada@example.com",
    sender_email: "noreply@example.com",
    subject: "Re: Your enquiry",
    body_text: "Checking in on your enquiry.",
    provider: "fake-email",
    provider_message_id: "msg_ops_1",
    failure_category: null,
    error: null,
    started_at: "2026-09-11T10:00:00Z",
    completed_at: "2026-09-11T10:00:01Z",
    created_at: "2026-09-11T10:00:00Z",
    updated_at: "2026-09-11T10:00:01Z",
    duration_ms: 1000,
    provider_idempotency_key: "follow-up:fu-1:attempt:1",
    ...overrides,
  };
}

describe("Follow-up operations", () => {
  beforeEach(() => {
    getFollowUpOperationsMock.mockReset();
    getLeadMock.mockReset();
    getLeadFollowUpExecutionsMock.mockReset();
    getLeadFollowUpsMock.mockReset();
    completeLeadFollowUpMock.mockReset();
    getLeadFollowUpsMock.mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      total: 0,
    });
    getLeadFollowUpExecutionsMock.mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      total: 0,
    });
  });

  it("shows a loading state without fabricated rows", () => {
    getFollowUpOperationsMock.mockReturnValue(new Promise(() => undefined));
    render(<FollowUpOperations />);
    expect(screen.getByText("Loading Overdue")).toBeInTheDocument();
    expect(screen.getByText("Loading records")).toBeInTheDocument();
    expect(screen.queryByText("Ada Prospect")).not.toBeInTheDocument();
    expect(screen.queryByText("Example")).not.toBeInTheDocument();
  });

  it("shows an empty state from real zero counts", async () => {
    getFollowUpOperationsMock.mockResolvedValue(page([]));
    render(<FollowUpOperations />);
    expect(
      await screen.findByRole("heading", { name: "No follow-ups yet" }),
    ).toBeVisible();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("Example")).not.toBeInTheDocument();
    const cards = screen.getAllByRole("article");
    expect(within(cards[0]).getByText("Overdue")).toBeVisible();
    expect(within(cards[0]).getByText("0")).toBeVisible();
  });

  it("shows an error state with retry", async () => {
    const user = userEvent.setup();
    getFollowUpOperationsMock.mockRejectedValueOnce(
      new ApiError("unavailable", 503),
    );
    getFollowUpOperationsMock.mockResolvedValueOnce(page([]));
    render(<FollowUpOperations />);
    expect(
      await screen.findByText("Follow-ups could not be loaded"),
    ).toBeVisible();
    expect(screen.queryByText("Ada Prospect")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("heading", { name: "No follow-ups yet" }),
    ).toBeVisible();
  });

  it("renders overdue, completed, cancelled, sent and failed states from the API", async () => {
    getFollowUpOperationsMock.mockResolvedValue(
      page(
        [
          item(),
          item({
            follow_up: followUp({
              id: "fu-2",
              status: "COMPLETED",
              is_overdue: false,
              completed_at: "2026-09-11T10:00:02Z",
            }),
            latest_execution: {
              id: "ex-1",
              status: "SENT",
              attempt: 1,
              recipient_email: "ada@example.com",
              provider: "fake-email",
              provider_message_id: "msg_ops_1",
              failure_category: null,
              error: null,
              started_at: "2026-09-11T10:00:00Z",
              completed_at: "2026-09-11T10:00:01Z",
              duration_ms: 1000,
            },
          }),
          item({
            follow_up: followUp({
              id: "fu-3",
              status: "CANCELLED",
              is_overdue: false,
              cancelled_at: "2026-09-11T09:00:00Z",
            }),
          }),
          item({
            follow_up: followUp({
              id: "fu-4",
              status: "PENDING",
              is_overdue: false,
              due_at: "2030-06-15T10:30:00Z",
            }),
            latest_execution: {
              id: "ex-2",
              status: "FAILED",
              attempt: 1,
              recipient_email: "ada@example.com",
              provider: "fake-email",
              provider_message_id: null,
              failure_category: "PROVIDER_ERROR",
              error: "Email provider request failed",
              started_at: "2026-09-11T10:00:00Z",
              completed_at: "2026-09-11T10:00:01Z",
              duration_ms: 800,
            },
          }),
        ],
        { summary: { overdue: 1, due_today: 0, upcoming: 1, completed: 1, cancelled: 1 } },
      ),
    );
    render(<FollowUpOperations />);
    const table = await screen.findByRole("table");
    expect(within(table).getAllByText("Ada Prospect").length).toBeGreaterThan(0);
    expect(within(table).getByText("Overdue")).toBeVisible();
    expect(within(table).getByText("Completed")).toBeVisible();
    expect(within(table).getByText("Cancelled")).toBeVisible();
    expect(within(table).getByText("Sent")).toBeVisible();
    expect(within(table).getByText("Failed")).toBeVisible();
    expect(within(table).getAllByText("Not sent yet").length).toBeGreaterThan(0);
    expect(screen.queryByText("Checking in on your enquiry.")).not.toBeInTheDocument();
    const cards = screen.getAllByRole("article");
    expect(within(cards[0]).getByText("1")).toBeVisible();
    expect(within(cards[2]).getByText("1")).toBeVisible();
  });

  it("does not imply an email was sent without a SENT execution", async () => {
    getFollowUpOperationsMock.mockResolvedValue(page([item()]));
    render(<FollowUpOperations />);
    const table = await screen.findByRole("table");
    expect(within(table).getByText("Not sent yet")).toBeVisible();
    expect(within(table).queryByText("Sent")).not.toBeInTheDocument();
  });

  it("refetches after a real mutation and when filters change", async () => {
    const user = userEvent.setup();
    getFollowUpOperationsMock
      .mockResolvedValueOnce(page([item()]))
      .mockResolvedValueOnce(page([]))
      .mockResolvedValue(page([]));
    getLeadMock.mockResolvedValue(lead);
    getLeadFollowUpsMock.mockResolvedValue({
      items: [followUp()],
      limit: 20,
      offset: 0,
      total: 1,
    });
    completeLeadFollowUpMock.mockResolvedValue(
      followUp({ status: "COMPLETED", is_overdue: false }),
    );
    render(<FollowUpOperations />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "Manage" })[0]);
    expect(await screen.findByRole("dialog")).toBeVisible();
    await user.click(await screen.findByRole("button", { name: "Complete" }));
    await waitFor(() => {
      expect(completeLeadFollowUpMock).toHaveBeenCalled();
      expect(getFollowUpOperationsMock).toHaveBeenCalledTimes(2);
    });
    await user.click(screen.getByRole("button", { name: "Close" }));
    await user.selectOptions(screen.getByLabelText("Follow-up status"), "COMPLETED");
    await waitFor(() => {
      expect(getFollowUpOperationsMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: "COMPLETED" }),
      );
    });
  });

  it("opens delivery history with safe execution fields only", async () => {
    const user = userEvent.setup();
    getFollowUpOperationsMock.mockResolvedValue(
      page([
        item({
          latest_execution: {
            id: "ex-1",
            status: "SENT",
            attempt: 1,
            recipient_email: "ada@example.com",
            provider: "fake-email",
            provider_message_id: "msg_ops_1",
            failure_category: null,
            error: null,
            started_at: "2026-09-11T10:00:00Z",
            completed_at: "2026-09-11T10:00:01Z",
            duration_ms: 1000,
          },
        }),
      ]),
    );
    getLeadFollowUpExecutionsMock.mockResolvedValue({
      items: [sentExecution()],
      limit: 20,
      offset: 0,
      total: 1,
    });
    render(<FollowUpOperations />);
    await screen.findByRole("table");
    await user.click(screen.getAllByRole("button", { name: "History" })[0]);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Delivery history")).toBeVisible();
    expect(within(dialog).getByText("ada@example.com")).toBeVisible();
    expect(within(dialog).getByText("fake-email")).toBeVisible();
    expect(within(dialog).getByText("msg_ops_1")).toBeVisible();
    expect(within(dialog).getByText("Sent")).toBeVisible();
    expect(within(dialog).queryByText("Checking in on your enquiry.")).not.toBeInTheDocument();
    expect(within(dialog).queryByText("sk-")).not.toBeInTheDocument();
  });

  it("exposes status and due filters accessibly", async () => {
    getFollowUpOperationsMock.mockResolvedValue(page([]));
    render(<FollowUpOperations />);
    await screen.findByRole("heading", { name: "No follow-ups yet" });
    expect(screen.getByLabelText("Follow-up status")).toBeVisible();
    expect(screen.getByLabelText("Due window")).toBeVisible();
  });
});
