import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UserMenu } from "@/components/layout/user-menu";
import { ApiError } from "@/lib/api/client";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  listMyOrganizations: vi.fn(),
  onSwitchOrganization: vi.fn(),
  onSignOut: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api/invitations", () => ({
  listMyOrganizations: mocks.listMyOrganizations,
}));

const user = {
  id: "user-1",
  name: "Alex Morgan",
  email: "alex@example.com",
};

describe("organization switching", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.listMyOrganizations.mockReset();
    mocks.onSwitchOrganization.mockReset();
    mocks.onSignOut.mockReset();
    mocks.listMyOrganizations.mockResolvedValue([
      {
        organization_id: "org-1",
        name: "Northstar Operations",
        role: "OWNER",
        membership_id: "membership-1",
      },
      {
        organization_id: "org-2",
        name: "Ada Org",
        role: "MEMBER",
        membership_id: "membership-2",
      },
    ]);
    mocks.onSwitchOrganization.mockResolvedValue(undefined);
  });

  it("lists memberships and switches through the supplied callback", async () => {
    const actor = userEvent.setup();
    render(
      <UserMenu
        user={user}
        organizationName="Northstar Operations"
        organizationId="org-1"
        role="OWNER"
        onSignOut={mocks.onSignOut}
        onSwitchOrganization={mocks.onSwitchOrganization}
      />,
    );

    await actor.click(
      screen.getByRole("button", { name: "Open user menu for Alex Morgan" }),
    );
    expect(await screen.findByRole("menuitem", { name: "Ada Org" })).toBeVisible();
    expect(
      screen.getByRole("menuitem", { name: "Northstar Operations (current)" }),
    ).toHaveAttribute("aria-disabled", "true");

    await actor.click(screen.getByRole("menuitem", { name: "Ada Org" }));
    await waitFor(() => expect(mocks.onSwitchOrganization).toHaveBeenCalledWith("org-2"));
    expect(mocks.onSwitchOrganization).not.toHaveBeenCalledWith("org-1");
  });

  it("shows an error when switching organization fails", async () => {
    const actor = userEvent.setup();
    mocks.onSwitchOrganization.mockRejectedValue(
      new ApiError("Request failed: 404", 404, { detail: "Organization not found" }),
    );
    render(
      <UserMenu
        user={user}
        organizationName="Northstar Operations"
        organizationId="org-1"
        role="OWNER"
        onSignOut={mocks.onSignOut}
        onSwitchOrganization={mocks.onSwitchOrganization}
      />,
    );

    await actor.click(
      screen.getByRole("button", { name: "Open user menu for Alex Morgan" }),
    );
    await actor.click(await screen.findByRole("menuitem", { name: "Ada Org" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Organization not found");
  });
});
