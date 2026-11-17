import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TeamPeopleSettings } from "@/components/settings/team-people-settings";

const mocks = vi.hoisted(() => ({
  listMembers: vi.fn(),
  updateMemberRole: vi.fn(),
  removeMember: vi.fn(),
  leaveOrganization: vi.fn(),
  completeAuth: vi.fn(),
  signOut: vi.fn(),
  listInvitations: vi.fn(),
  createInvitation: vi.fn(),
  revokeInvitation: vi.fn(),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    completeAuth: mocks.completeAuth,
    signOut: mocks.signOut,
  }),
}));

vi.mock("@/lib/api/members", () => ({
  listMembers: mocks.listMembers,
  updateMemberRole: mocks.updateMemberRole,
  removeMember: mocks.removeMember,
  leaveOrganization: mocks.leaveOrganization,
}));

vi.mock("@/lib/api/invitations", () => ({
  listInvitations: mocks.listInvitations,
  createInvitation: mocks.createInvitation,
  revokeInvitation: mocks.revokeInvitation,
}));

const owner = {
  membership_id: "membership-1",
  role: "OWNER" as const,
  user: {
    id: "user-1",
    name: "Alex Morgan",
    email: "alex@example.com",
  },
};

const member = {
  membership_id: "membership-2",
  role: "MEMBER" as const,
  user: {
    id: "user-2",
    name: "Jordan Lee",
    email: "jordan@example.com",
  },
};

async function openMemberActions(
  user: ReturnType<typeof userEvent.setup>,
  name: string,
) {
  await user.click(screen.getByRole("button", { name: `Actions for ${name}` }));
}

describe("TeamPeopleSettings", () => {
  beforeEach(() => {
    mocks.listMembers.mockReset();
    mocks.updateMemberRole.mockReset();
    mocks.removeMember.mockReset();
    mocks.leaveOrganization.mockReset();
    mocks.completeAuth.mockReset();
    mocks.signOut.mockReset();
    mocks.listInvitations.mockReset();
    mocks.createInvitation.mockReset();
    mocks.revokeInvitation.mockReset();
    mocks.listMembers.mockResolvedValue([owner, member]);
    mocks.listInvitations.mockResolvedValue([]);
  });

  it("shows people and lets an owner change a member role after confirm", async () => {
    const user = userEvent.setup();
    mocks.updateMemberRole.mockResolvedValue({
      ...member,
      role: "ADMIN",
    });

    render(
      <TeamPeopleSettings
        role="OWNER"
        currentUserId="user-1"
        currentMembershipId="membership-1"
      />,
    );

    expect(await screen.findByText("Jordan Lee")).toBeVisible();
    expect(screen.getByText("jordan@example.com")).toBeVisible();
    expect(screen.getByText("(you)")).toBeVisible();

    await openMemberActions(user, "Jordan Lee");
    await user.click(
      await screen.findByRole("menuitem", { name: "Make Admin" }),
    );
    expect(
      screen.getByRole("heading", { name: "Change role to Admin?" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Change role" }));

    await waitFor(() =>
      expect(mocks.updateMemberRole).toHaveBeenCalledWith(
        "membership-2",
        "ADMIN",
      ),
    );
    const jordanRow = screen.getByText("Jordan Lee").closest("li");
    expect(jordanRow).not.toBeNull();
    expect(within(jordanRow as HTMLElement).getByText("Admin")).toBeVisible();
  });

  it("lets an owner remove a member after confirm", async () => {
    const user = userEvent.setup();
    mocks.removeMember.mockResolvedValue(undefined);

    render(
      <TeamPeopleSettings
        role="OWNER"
        currentUserId="user-1"
        currentMembershipId="membership-1"
      />,
    );

    await screen.findByText("Jordan Lee");
    await openMemberActions(user, "Jordan Lee");
    await user.click(
      await screen.findByRole("menuitem", {
        name: "Remove from organization",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() =>
      expect(mocks.removeMember).toHaveBeenCalledWith("membership-2"),
    );
    expect(screen.queryByText("Jordan Lee")).not.toBeInTheDocument();
  });

  it("lets a member leave and signs out when no other organization remains", async () => {
    const user = userEvent.setup();
    mocks.leaveOrganization.mockResolvedValue(undefined);

    render(
      <TeamPeopleSettings
        role="MEMBER"
        currentUserId="user-2"
        currentMembershipId="membership-2"
      />,
    );

    await screen.findByText("Jordan Lee");
    await openMemberActions(user, "Jordan Lee");
    await user.click(
      await screen.findByRole("menuitem", { name: "Leave organization" }),
    );
    const dialog = screen.getByRole("dialog");
    await user.click(
      within(dialog).getByRole("button", { name: "Leave organization" }),
    );

    await waitFor(() => expect(mocks.leaveOrganization).toHaveBeenCalledOnce());
    expect(mocks.signOut).toHaveBeenCalledOnce();
    expect(mocks.completeAuth).not.toHaveBeenCalled();
  });

  it("applies a switched organization session after leave", async () => {
    const user = userEvent.setup();
    const auth = {
      access_token: "next-token",
      token_type: "bearer",
      user: member.user,
      organization: {
        id: "org-2",
        name: "Other Org",
        slug: "other-org",
        website_capture_enabled: false,
        default_currency: "USD",
      },
      membership: {
        id: "membership-9",
        role: "MEMBER",
        organization_id: "org-2",
        user_id: "user-2",
      },
      email_verified: true,
    };
    mocks.leaveOrganization.mockResolvedValue(auth);
    mocks.listMembers.mockResolvedValue([owner, member]);

    render(
      <TeamPeopleSettings
        role="MEMBER"
        currentUserId="user-2"
        currentMembershipId="membership-2"
      />,
    );

    await screen.findByText("Jordan Lee");
    await openMemberActions(user, "Jordan Lee");
    await user.click(
      await screen.findByRole("menuitem", { name: "Leave organization" }),
    );
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Leave organization",
      }),
    );

    await waitFor(() => expect(mocks.completeAuth).toHaveBeenCalledWith(auth));
    expect(mocks.signOut).not.toHaveBeenCalled();
  });

  it("hides destructive controls from members for other people", async () => {
    render(
      <TeamPeopleSettings
        role="MEMBER"
        currentUserId="user-2"
        currentMembershipId="membership-2"
      />,
    );

    expect(await screen.findByText("Alex Morgan")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Actions for Alex Morgan" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Actions for Jordan Lee" }),
    ).toBeVisible();
  });
});
