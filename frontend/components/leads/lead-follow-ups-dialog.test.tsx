import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LeadFollowUpsDialog } from "@/components/leads/lead-follow-ups-dialog";
import { ApiError } from "@/lib/api/client";
import {
  cancelLeadFollowUp,
  completeLeadFollowUp,
  createLeadFollowUp,
  getLeadFollowUps,
  updateLeadFollowUp,
} from "@/lib/api/leads";
import type { Lead, LeadFollowUp } from "@/types/api";

vi.mock("@/lib/api/leads", () => ({
  getLeadFollowUps: vi.fn(),
  createLeadFollowUp: vi.fn(),
  updateLeadFollowUp: vi.fn(),
  completeLeadFollowUp: vi.fn(),
  cancelLeadFollowUp: vi.fn(),
}));

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
    due_at: "2030-06-15T10:30:00.000Z",
    notes: "Check reply",
    body_text: "Checking in on your enquiry.",
    revision: 1,
    is_overdue: false,
    completed_at: null,
    cancelled_at: null,
    created_at: "2026-09-10T10:00:00Z",
    updated_at: "2026-09-10T10:00:00Z",
    ...overrides,
  };
}

const getLeadFollowUpsMock = vi.mocked(getLeadFollowUps);
const createLeadFollowUpMock = vi.mocked(createLeadFollowUp);
const updateLeadFollowUpMock = vi.mocked(updateLeadFollowUp);
const completeLeadFollowUpMock = vi.mocked(completeLeadFollowUp);
const cancelLeadFollowUpMock = vi.mocked(cancelLeadFollowUp);

describe("Lead follow-ups dialog", () => {
  beforeEach(() => {
    getLeadFollowUpsMock.mockReset();
    createLeadFollowUpMock.mockReset();
    updateLeadFollowUpMock.mockReset();
    completeLeadFollowUpMock.mockReset();
    cancelLeadFollowUpMock.mockReset();
    getLeadFollowUpsMock.mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      total: 0,
    });
  });

  it("shows an empty state and loading", async () => {
    getLeadFollowUpsMock.mockReturnValue(new Promise(() => undefined));
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading follow-ups");
  });

  it("creates a follow-up from the real API and prevents duplicate submit", async () => {
    const user = userEvent.setup();
    createLeadFollowUpMock.mockResolvedValue(followUp());
    getLeadFollowUpsMock
      .mockResolvedValueOnce({ items: [], limit: 20, offset: 0, total: 0 })
      .mockResolvedValueOnce({
        items: [followUp()],
        limit: 20,
        offset: 0,
        total: 1,
      });
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    expect(await screen.findByText("No follow-ups yet.")).toBeVisible();
    await user.type(screen.getByLabelText(/Due date and time/), "2030-06-15T10:30");
    await user.type(screen.getByLabelText(/Email body/), "Checking in on your enquiry.");
    await user.click(screen.getByRole("button", { name: "Create follow-up" }));
    await waitFor(() => {
      expect(createLeadFollowUpMock).toHaveBeenCalledTimes(1);
    });
    const payload = createLeadFollowUpMock.mock.calls[0]?.[1];
    expect(payload).not.toHaveProperty("organization_id");
    expect(payload?.type).toBe("EMAIL_FOLLOW_UP");
    expect(payload?.body_text).toBe("Checking in on your enquiry.");
    expect(await screen.findByText("PENDING")).toBeVisible();
    expect(screen.getAllByText("Email follow-up").length).toBeGreaterThan(0);
    expect(screen.getByText("Checking in on your enquiry.")).toBeVisible();
  });

  it("requires email body for email follow-ups and does not submit", async () => {
    const user = userEvent.setup();
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    await screen.findByText("No follow-ups yet.");
    await user.type(screen.getByLabelText(/Due date and time/), "2030-06-15T10:30");
    await user.type(screen.getByLabelText(/Email body/), "   ");
    expect(screen.getByRole("button", { name: "Create follow-up" })).toBeDisabled();
    expect(createLeadFollowUpMock).not.toHaveBeenCalled();
  });

  it("does not require email body for manual follow-ups", async () => {
    const user = userEvent.setup();
    createLeadFollowUpMock.mockResolvedValue(
      followUp({ type: "MANUAL_FOLLOW_UP", body_text: null, notes: "Call them" }),
    );
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    await screen.findByText("No follow-ups yet.");
    await user.selectOptions(screen.getByLabelText(/^Type/), "MANUAL_FOLLOW_UP");
    expect(screen.queryByLabelText(/Email body/)).not.toBeInTheDocument();
    await user.type(screen.getByLabelText(/Due date and time/), "2030-06-15T10:30");
    await user.type(screen.getByLabelText(/^Notes/), "Call them");
    await user.click(screen.getByRole("button", { name: "Create follow-up" }));
    await waitFor(() => {
      expect(createLeadFollowUpMock).toHaveBeenCalledTimes(1);
    });
    expect(createLeadFollowUpMock.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({
        type: "MANUAL_FOLLOW_UP",
        notes: "Call them",
      }),
    );
    expect(createLeadFollowUpMock.mock.calls[0]?.[1]).not.toHaveProperty("body_text");
  });

  it("shows overdue and can complete, reschedule, and cancel", async () => {
    const user = userEvent.setup();
    getLeadFollowUpsMock.mockResolvedValue({
      items: [followUp({ is_overdue: true, notes: "Late" })],
      limit: 20,
      offset: 0,
      total: 1,
    });
    completeLeadFollowUpMock.mockResolvedValue(
      followUp({ status: "COMPLETED", is_overdue: false, revision: 2 }),
    );
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    expect(await screen.findByText("OVERDUE")).toBeVisible();
    getLeadFollowUpsMock.mockResolvedValue({
      items: [followUp({ status: "COMPLETED", is_overdue: false, revision: 2 })],
      limit: 20,
      offset: 0,
      total: 1,
    });
    await user.click(screen.getByRole("button", { name: "Complete" }));
    expect(completeLeadFollowUpMock).toHaveBeenCalledWith("lead-1", "fu-1", {
      expected_revision: 1,
    });
    expect(await screen.findByText("COMPLETED")).toBeVisible();
  });

  it("reschedules a pending follow-up", async () => {
    const user = userEvent.setup();
    getLeadFollowUpsMock.mockResolvedValue({
      items: [followUp()],
      limit: 20,
      offset: 0,
      total: 1,
    });
    updateLeadFollowUpMock.mockResolvedValue(followUp({ revision: 2 }));
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    await screen.findByText("PENDING");
    await user.click(screen.getByRole("button", { name: "Reschedule" }));
    const due = screen.getByLabelText(/New due date and time/);
    await user.clear(due);
    await user.type(due, "2030-07-01T09:00");
    getLeadFollowUpsMock.mockResolvedValue({
      items: [followUp({ revision: 2 })],
      limit: 20,
      offset: 0,
      total: 1,
    });
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(updateLeadFollowUpMock).toHaveBeenCalledWith(
      "lead-1",
      "fu-1",
      expect.objectContaining({
        expected_revision: 1,
        body_text: "Checking in on your enquiry.",
      }),
    );
  });

  it("updates the stored email body on a pending follow-up", async () => {
    const user = userEvent.setup();
    getLeadFollowUpsMock.mockResolvedValue({
      items: [followUp()],
      limit: 20,
      offset: 0,
      total: 1,
    });
    updateLeadFollowUpMock.mockResolvedValue(
      followUp({ revision: 2, body_text: "Updated body" }),
    );
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    await screen.findByText("PENDING");
    await user.click(screen.getByRole("button", { name: "Reschedule" }));
    const body = screen.getByLabelText(/Edit email body/);
    await user.clear(body);
    await user.type(body, "Updated body");
    getLeadFollowUpsMock.mockResolvedValue({
      items: [followUp({ revision: 2, body_text: "Updated body" })],
      limit: 20,
      offset: 0,
      total: 1,
    });
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(updateLeadFollowUpMock).toHaveBeenCalledWith(
      "lead-1",
      "fu-1",
      expect.objectContaining({ expected_revision: 1, body_text: "Updated body" }),
    );
  });

  it("shows saving and create error states without duplicate submits", async () => {
    const user = userEvent.setup();
    let resolveCreate: (value: LeadFollowUp) => void = () => undefined;
    createLeadFollowUpMock.mockImplementation(
      () =>
        new Promise<LeadFollowUp>((resolve) => {
          resolveCreate = resolve;
        }),
    );
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    await screen.findByText("No follow-ups yet.");
    await user.type(screen.getByLabelText(/Due date and time/), "2030-06-15T10:30");
    await user.type(screen.getByLabelText(/Email body/), "Checking in on your enquiry.");
    await user.click(screen.getByRole("button", { name: "Create follow-up" }));
    expect(await screen.findByRole("button", { name: "Saving…" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Saving…" }));
    expect(createLeadFollowUpMock).toHaveBeenCalledTimes(1);
    resolveCreate(followUp());
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Create follow-up" })).toBeInTheDocument();
    });
    expect(createLeadFollowUpMock).toHaveBeenCalledTimes(1);
  });

  it("maps create 422 errors", async () => {
    const user = userEvent.setup();
    createLeadFollowUpMock.mockRejectedValue(
      new ApiError("Request failed: 422", 422, { detail: "invalid" }),
    );
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    await screen.findByText("No follow-ups yet.");
    await user.type(screen.getByLabelText(/Due date and time/), "2030-06-15T10:30");
    await user.type(screen.getByLabelText(/Email body/), "Checking in on your enquiry.");
    await user.click(screen.getByRole("button", { name: "Create follow-up" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Review the due date, type, and email body, then try again.",
    );
  });

  it("does not offer send or execution actions", async () => {
    getLeadFollowUpsMock.mockResolvedValue({
      items: [followUp()],
      limit: 20,
      offset: 0,
      total: 1,
    });
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    await screen.findByText("PENDING");
    expect(screen.queryByRole("button", { name: /send now/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/scheduled/i)).not.toBeInTheDocument();
  });

  it("cancels after confirmation and maps 409", async () => {
    const user = userEvent.setup();
    getLeadFollowUpsMock.mockResolvedValue({
      items: [followUp()],
      limit: 20,
      offset: 0,
      total: 1,
    });
    cancelLeadFollowUpMock.mockRejectedValue(
      new ApiError("Request failed: 409", 409, { detail: "changed" }),
    );
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    await screen.findByRole("button", { name: "Cancel follow-up" });
    await user.click(screen.getByRole("button", { name: "Cancel follow-up" }));
    expect(screen.getByRole("heading", { name: "Cancel this follow-up?" })).toBeVisible();
    await user.click(screen.getAllByRole("button", { name: "Cancel follow-up" }).at(-1)!);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This follow-up changed. Refresh and review the latest status.",
    );
  });

  it("maps 403 and 404 errors", async () => {
    getLeadFollowUpsMock.mockRejectedValueOnce(
      new ApiError("Request failed: 403", 403, { detail: "forbidden" }),
    );
    const first = render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You do not have permission to manage follow-ups.",
    );
    first.unmount();
    getLeadFollowUpsMock.mockRejectedValueOnce(
      new ApiError("Request failed: 404", 404, { detail: "missing" }),
    );
    render(
      <LeadFollowUpsDialog open lead={lead} onOpenChange={() => undefined} />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This follow-up could not be found.",
    );
  });
});
