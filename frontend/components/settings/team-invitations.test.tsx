import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamInvitations } from "@/components/settings/team-invitations";
import { ApiError } from "@/lib/api/client";

const mocks = vi.hoisted(() => ({
  listInvitations: vi.fn(),
  listInvitationHistory: vi.fn(),
  createInvitation: vi.fn(),
  revokeInvitation: vi.fn(),
  resendInvitation: vi.fn(),
}));

vi.mock("@/lib/api/invitations", () => ({
  listInvitations: mocks.listInvitations,
  listInvitationHistory: mocks.listInvitationHistory,
  createInvitation: mocks.createInvitation,
  revokeInvitation: mocks.revokeInvitation,
  resendInvitation: mocks.resendInvitation,
}));

const pending = [
  {
    id: "invite-1",
    email: "ada@example.com",
    role: "ADMIN",
    expires_at: "2026-12-01T12:00:00.000Z",
    created_at: "2026-11-16T12:00:00.000Z",
  },
];

describe("team invitations", () => {
  beforeEach(() => {
    mocks.listInvitations.mockReset();
    mocks.listInvitationHistory.mockReset();
    mocks.createInvitation.mockReset();
    mocks.revokeInvitation.mockReset();
    mocks.resendInvitation.mockReset();
    mocks.listInvitations.mockResolvedValue(pending);
    mocks.listInvitationHistory.mockResolvedValue([
      {
        id: "invite-old",
        email: "old@example.com",
        role: "MEMBER",
        status: "revoked",
        created_at: "2026-11-01T12:00:00.000Z",
        resolved_at: "2026-11-02T12:00:00.000Z",
      },
    ]);
  });

  it("lets an owner invite an admin, resend, and revoke a pending invitation", async () => {
    const user = userEvent.setup();
    mocks.createInvitation.mockResolvedValue({ status: "accepted" });
    mocks.resendInvitation.mockResolvedValue({
      ...pending[0],
      expires_at: "2026-12-08T12:00:00.000Z",
    });
    mocks.revokeInvitation.mockResolvedValue(undefined);

    render(<TeamInvitations role="OWNER" />);

    expect(await screen.findByText("ada@example.com")).toBeVisible();
    expect(screen.getByText(/Expires/)).toHaveTextContent("Admin");
    expect(screen.getByLabelText(/^role/i)).toBeVisible();
    expect(screen.getByText("old@example.com")).toBeVisible();
    expect(screen.getByText(/Revoked/)).toBeVisible();

    await user.type(screen.getByLabelText(/^email/i), "new@example.com");
    await user.selectOptions(screen.getByLabelText(/^role/i), "ADMIN");
    await user.click(screen.getByRole("button", { name: "Send invitation" }));

    await waitFor(() =>
      expect(mocks.createInvitation).toHaveBeenCalledWith("new@example.com", "ADMIN"),
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "If this address can join the organization and the email can be delivered, the invitation appears in the pending list.",
    );

    await user.click(screen.getByRole("button", { name: "Resend" }));
    await waitFor(() => expect(mocks.resendInvitation).toHaveBeenCalledWith("invite-1"));
    expect(screen.getByRole("status")).toHaveTextContent("Invitation email resent.");

    await user.click(screen.getByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(mocks.revokeInvitation).toHaveBeenCalledWith("invite-1"));
    expect(screen.queryByText("ada@example.com")).not.toBeInTheDocument();
  });

  it("lets an admin invite only a member", async () => {
    const user = userEvent.setup();
    mocks.createInvitation.mockResolvedValue({ status: "accepted" });

    render(<TeamInvitations role="ADMIN" />);

    expect(await screen.findByText("ada@example.com")).toBeVisible();
    expect(screen.queryByLabelText(/^role/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Revoke" })).not.toBeInTheDocument();
    expect(screen.getByText(/Admins can invite members/)).toBeVisible();
    await user.type(screen.getByLabelText(/^email/i), "member@example.com");
    await user.click(screen.getByRole("button", { name: "Send invitation" }));

    await waitFor(() =>
      expect(mocks.createInvitation).toHaveBeenCalledWith("member@example.com", "MEMBER"),
    );
  });

  it("lets an admin revoke a member invitation", async () => {
    const user = userEvent.setup();
    mocks.listInvitations.mockResolvedValue([
      {
        id: "invite-2",
        email: "member@example.com",
        role: "MEMBER",
        expires_at: "2026-12-01T12:00:00.000Z",
        created_at: "2026-11-16T12:00:00.000Z",
      },
    ]);
    mocks.revokeInvitation.mockResolvedValue(undefined);

    render(<TeamInvitations role="ADMIN" />);
    await user.click(await screen.findByRole("button", { name: "Revoke" }));

    await waitFor(() => expect(mocks.revokeInvitation).toHaveBeenCalledWith("invite-2"));
  });

  it("does not offer invitations to a member", () => {
    render(<TeamInvitations role="MEMBER" />);

    expect(screen.getByText(/Only owners and admins can invite/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Send invitation" })).not.toBeInTheDocument();
    expect(mocks.listInvitations).not.toHaveBeenCalled();
  });

  it("shows a resend failure without removing the invitation", async () => {
    const user = userEvent.setup();
    mocks.resendInvitation.mockRejectedValue(
      new ApiError("Request failed: 422", 422, {
        detail: "The invitation email could not be delivered.",
      }),
    );

    render(<TeamInvitations role="OWNER" />);
    await screen.findByText("ada@example.com");
    await user.click(screen.getByRole("button", { name: "Resend" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The invitation email could not be delivered.",
    );
  });

  it("shows a revoke failure without removing the invitation", async () => {
    const user = userEvent.setup();
    mocks.revokeInvitation.mockRejectedValue(
      new ApiError("Request failed: 403", 403, {
        detail: "Not allowed to revoke this invitation",
      }),
    );

    render(<TeamInvitations role="OWNER" />);
    await screen.findByText("ada@example.com");
    await user.click(screen.getByRole("button", { name: "Revoke" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Not allowed to revoke this invitation",
    );
    expect(screen.getByText("ada@example.com")).toBeVisible();
  });
});
