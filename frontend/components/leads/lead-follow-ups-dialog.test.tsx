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
    await user.type(screen.getByLabelText(/^Notes/), "Check reply");
    await user.click(screen.getByRole("button", { name: "Create follow-up" }));
    await waitFor(() => {
      expect(createLeadFollowUpMock).toHaveBeenCalledTimes(1);
    });
    const payload = createLeadFollowUpMock.mock.calls[0]?.[1];
    expect(payload).not.toHaveProperty("organization_id");
    expect(payload?.type).toBe("EMAIL_FOLLOW_UP");
    expect(payload?.notes).toBe("Check reply");
    expect(await screen.findByText("PENDING")).toBeVisible();
    expect(screen.getAllByText("Email follow-up").length).toBeGreaterThan(0);
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
      expect.objectContaining({ expected_revision: 1 }),
    );
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
