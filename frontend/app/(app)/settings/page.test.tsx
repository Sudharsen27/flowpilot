import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SettingsPage from "@/app/(app)/settings/page";

const { apiGet, signOut, authState } = vi.hoisted(() => {
  const signOut = vi.fn();
  return {
    apiGet: vi.fn(),
    signOut,
    authState: {
      isLoading: false,
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
          role: "OWNER" as const,
        },
      },
      signOut,
    },
  };
});

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => authState,
}));

vi.mock("@/lib/api/client", () => ({
  apiGet,
}));

describe("identity-backed settings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders authenticated identity and real organization members", async () => {
    apiGet.mockResolvedValue([
      {
        membership_id: "membership-1",
        role: "OWNER",
        user: authState.session.user,
      },
      {
        membership_id: "membership-2",
        role: "MEMBER",
        user: {
          id: "user-2",
          name: "Jordan Lee",
          email: "jordan@example.com",
        },
      },
    ]);

    render(<SettingsPage />);

    expect(screen.getByRole("heading", { name: "Settings" })).toBeVisible();
    expect(screen.getByText("alex@example.com")).toBeVisible();
    expect(screen.getAllByText("Northstar Operations")).not.toHaveLength(0);
    expect(screen.getByText("northstar-operations")).toBeVisible();
    expect(screen.getAllByText("Owner")).not.toHaveLength(0);

    await waitFor(() =>
      expect(apiGet).toHaveBeenCalledWith(
        "/api/v1/organizations/current/members",
      ),
    );
    expect(screen.getAllByText("Jordan Lee")).not.toHaveLength(0);
    expect(screen.getAllByText("jordan@example.com")).not.toHaveLength(0);
    expect(screen.getAllByText("Member")).not.toHaveLength(0);
  });

  it("shows a member loading state while the request is pending", () => {
    apiGet.mockReturnValue(new Promise(() => undefined));

    render(<SettingsPage />);

    expect(screen.getByText("Loading records")).toBeInTheDocument();
  });

  it("shows a truthful empty state when no members are returned", async () => {
    apiGet.mockResolvedValue([]);

    render(<SettingsPage />);

    expect(
      await screen.findByRole("heading", { name: "No organization members" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "No members were returned for the current organization.",
      ),
    ).toBeVisible();
  });

  it("shows an error and retries the members request", async () => {
    const user = userEvent.setup();
    apiGet
      .mockRejectedValueOnce(new Error("Request failed"))
      .mockResolvedValueOnce([
        {
          membership_id: "membership-2",
          role: "MEMBER",
          user: {
            id: "user-2",
            name: "Jordan Lee",
            email: "jordan@example.com",
          },
        },
      ]);

    render(<SettingsPage />);

    expect(
      await screen.findByRole("heading", {
        name: "Members could not be loaded",
      }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(2));
    expect(screen.getAllByText("Jordan Lee")).not.toHaveLength(0);
  });

  it("delegates sign-out to the existing authentication mechanism", async () => {
    const user = userEvent.setup();
    apiGet.mockResolvedValue([]);

    render(<SettingsPage />);

    await user.click(screen.getByRole("button", { name: "Sign out" }));
    expect(signOut).toHaveBeenCalledOnce();
  });
});
