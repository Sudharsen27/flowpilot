import { StrictMode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InvitationAcceptPanel } from "@/app/invitations/accept/invitation-accept-panel";
import { ApiError } from "@/lib/api/client";

const state = vi.hoisted(() => ({ search: "token=invite-token" }));
const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  acceptInvitation: vi.fn(),
  logoutSession: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => mocks,
  useSearchParams: () => new URLSearchParams(state.search),
}));

vi.mock("@/lib/api/invitations", () => ({
  acceptInvitation: mocks.acceptInvitation,
}));

vi.mock("@/lib/api/auth", () => ({
  logoutSession: mocks.logoutSession,
}));

describe("invitation acceptance", () => {
  beforeEach(() => {
    state.search = "token=invite-token";
    mocks.replace.mockReset();
    mocks.acceptInvitation.mockReset();
    mocks.logoutSession.mockReset();
    window.localStorage.clear();
  });

  it("asks a new user for a name and password and does not store the token", async () => {
    const user = userEvent.setup();
    const created = {
      access_token: "session-token",
      token_type: "bearer",
      user: { id: "user-2", email: "ada@example.com", name: "Ada" },
      organization: { id: "org-2", name: "Owner Org", slug: "owner-org" },
      membership: {
        id: "membership-2",
        organization_id: "org-2",
        user_id: "user-2",
        role: "MEMBER" as const,
      },
      email_verified: true,
    };
    mocks.acceptInvitation.mockImplementation(
      (input: { name?: string }) =>
        input.name
          ? Promise.resolve(created)
          : Promise.reject(
              new ApiError("Request failed: 422", 422, {
                detail: "Name and password are required",
              }),
            ),
    );

    render(<InvitationAcceptPanel />);
    expect(mocks.acceptInvitation).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Accept invitation" }));

    expect(await screen.findByLabelText(/^name/i)).toBeVisible();
    expect(screen.queryByLabelText(/role/i)).not.toBeInTheDocument();
    await user.type(screen.getByLabelText(/^name/i), "Ada");
    await user.type(screen.getByLabelText(/^password/i), "password12");
    await user.click(screen.getByRole("button", { name: "Create account and join" }));

    await waitFor(() =>
      expect(mocks.acceptInvitation).toHaveBeenCalledWith({
        token: "invite-token",
        name: "Ada",
        password: "password12",
      }),
    );
    expect(mocks.replace).toHaveBeenCalledWith("/dashboard");
    expect(window.localStorage.getItem("flowpilot.access_token")).toBeNull();
    expect(document.body.textContent).not.toContain("invite-token");
  });

  it("sends an existing account to sign in and keeps the return path", async () => {
    mocks.acceptInvitation.mockResolvedValue({ status: "sign_in_required" });

    render(<InvitationAcceptPanel />);
    expect(screen.getByRole("link", { name: "Back to sign in" })).toHaveAttribute(
      "href",
      `/login?next=${encodeURIComponent("/invitations/accept?token=invite-token")}`,
    );

    await userEvent.click(screen.getByRole("button", { name: "Accept invitation" }));
    const link = await screen.findByRole("link", { name: "Sign in to accept" });
    expect(link).toHaveAttribute(
      "href",
      `/login?next=${encodeURIComponent("/invitations/accept?token=invite-token")}`,
    );
    expect(screen.getByText(/including Google/)).toBeVisible();
    expect(screen.queryByLabelText(/^password/i)).not.toBeInTheDocument();
  });

  it("accepts a signed-in account without switching the current workspace", async () => {
    mocks.acceptInvitation.mockResolvedValue({
      status: "accepted",
      organization_id: "org-2",
    });

    render(<InvitationAcceptPanel />);
    await userEvent.click(screen.getByRole("button", { name: "Accept invitation" }));

    expect(await screen.findByText(/This browser stays in the current workspace/)).toBeVisible();
    expect(screen.getByRole("link", { name: "Go to workspace" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("shows one invalid-link message and a signed-in mismatch", async () => {
    mocks.acceptInvitation.mockRejectedValue(
      new ApiError("Request failed: 400", 400, {
        detail: "This invitation link is invalid or has expired.",
      }),
    );
    const { unmount } = render(<InvitationAcceptPanel />);
    await userEvent.click(screen.getByRole("button", { name: "Accept invitation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This invitation link is invalid or has expired.",
    );
    unmount();

    mocks.acceptInvitation.mockRejectedValue(
      new ApiError("Request failed: 403", 403, {
        detail: "This invitation does not match the signed-in account.",
      }),
    );
    mocks.logoutSession.mockResolvedValue(undefined);
    render(<InvitationAcceptPanel />);
    await userEvent.click(screen.getByRole("button", { name: "Accept invitation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This invitation does not match the signed-in account.",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Sign out and use the invited account" }),
    );
    await waitFor(() => expect(mocks.logoutSession).toHaveBeenCalledOnce());
    expect(mocks.replace).toHaveBeenCalledWith(
      `/login?next=${encodeURIComponent("/invitations/accept?token=invite-token")}`,
    );
  });

  it("does not consume the invitation when React Strict Mode remounts the page", async () => {
    const user = userEvent.setup();
    mocks.acceptInvitation.mockResolvedValue({
      status: "accepted",
      organization_id: "org-2",
    });

    render(
      <StrictMode>
        <InvitationAcceptPanel />
      </StrictMode>,
    );

    expect(mocks.acceptInvitation).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Accept invitation" }));

    await waitFor(() => expect(mocks.acceptInvitation).toHaveBeenCalledTimes(1));
    expect(mocks.acceptInvitation).toHaveBeenCalledWith({ token: "invite-token" });
    expect(await screen.findByText(/This browser stays in the current workspace/)).toBeVisible();
  });

  it("ignores a second accept while the first request is in progress", async () => {
    const user = userEvent.setup();
    let release: (value: { status: "accepted"; organization_id: string }) => void = () => {};
    mocks.acceptInvitation.mockImplementation(
      () =>
        new Promise((resolve) => {
          release = resolve;
        }),
    );

    render(<InvitationAcceptPanel />);
    const button = screen.getByRole("button", { name: "Accept invitation" });
    await user.click(button);
    await user.click(button);

    expect(mocks.acceptInvitation).toHaveBeenCalledTimes(1);
    release({ status: "accepted", organization_id: "org-2" });
    expect(await screen.findByText(/This browser stays in the current workspace/)).toBeVisible();
  });
});
