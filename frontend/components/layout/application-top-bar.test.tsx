import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApplicationTopBar } from "@/components/layout/application-top-bar";

const { mockPush, mockSignOut } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockSignOut: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    session: {
      user: {
        id: "user-1",
        name: "Alex Morgan",
        email: "alex@example.com",
      },
      organization: {
        id: "org-1",
        name: "Northstar Operations",
        slug: "northstar-operations",
      },
      membership: {
        id: "membership-1",
        organization_id: "org-1",
        user_id: "user-1",
        role: "OWNER",
      },
    },
    signOut: mockSignOut,
  }),
}));

function renderTopBar() {
  return render(
    <ApplicationTopBar
      mobileNavigationTrigger={<button type="button">Navigation</button>}
    />,
  );
}

describe("authenticated application top bar", () => {
  it("renders real organization and user context", () => {
    renderTopBar();

    expect(screen.getByText("Current organization")).toBeVisible();
    expect(screen.getByText("Northstar Operations")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Open user menu for Alex Morgan" }),
    ).toBeVisible();
  });

  it("shows identity and role and signs out through the keyboard menu", async () => {
    const user = userEvent.setup();
    renderTopBar();

    const trigger = screen.getByRole("button", {
      name: "Open user menu for Alex Morgan",
    });
    trigger.focus();
    await user.keyboard("{Enter}");

    expect(screen.getByText("alex@example.com")).toBeVisible();
    expect(screen.getByText("Role: Owner")).toBeVisible();
    expect(
      within(screen.getByRole("menu")).getByText("Northstar Operations"),
    ).toBeVisible();

    const settings = await screen.findByRole("menuitem", { name: "Settings" });
    expect(settings).toHaveFocus();
    await user.keyboard("{ArrowDown}");

    const signOut = screen.getByRole("menuitem", { name: "Sign out" });
    expect(signOut).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(mockSignOut).toHaveBeenCalledOnce();
  });

  it("exposes search access without presenting fake results", async () => {
    const user = userEvent.setup();
    renderTopBar();

    await user.click(
      screen.getByRole("button", { name: "Open global search" }),
    );

    expect(screen.getByRole("dialog", { name: "Global search" })).toBeVisible();
    expect(
      screen.getByText(
        /Search across your FlowPilot workspace is not available yet/,
      ),
    ).toBeVisible();
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
