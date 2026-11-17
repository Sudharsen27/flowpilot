import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GuestRoute } from "@/components/auth/guest-route";
import { ProtectedRoute } from "@/components/auth/protected-route";
import type { Session } from "@/hooks/use-auth";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  useAuth: vi.fn(),
  pathname: "/dashboard",
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace }),
  usePathname: () => mocks.pathname,
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: mocks.useAuth,
}));

const session: Session = {
  user: { id: "user-1", email: "owner@example.com", name: "Owner" },
  organization: { id: "org-1", name: "Acme", slug: "acme" },
  membership: {
    id: "membership-1",
    organization_id: "org-1",
    user_id: "user-1",
    role: "OWNER",
  },
  emailVerified: true,
};

describe("authentication route boundaries", () => {
  beforeEach(() => {
    mocks.replace.mockReset();
    mocks.useAuth.mockReset();
    mocks.pathname = "/dashboard";
    window.history.replaceState({}, "", "/login");
  });

  it("redirects an unauthenticated product route without rendering its content", async () => {
    mocks.useAuth.mockReturnValue({ session: null, isLoading: false });

    render(
      <ProtectedRoute>
        <div>Private product route</div>
      </ProtectedRoute>,
    );

    expect(screen.queryByText("Private product route")).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/login"));
  });

  it("renders a product route for an authenticated session", () => {
    mocks.useAuth.mockReturnValue({ session, isLoading: false });

    render(
      <ProtectedRoute>
        <div>Private product route</div>
      </ProtectedRoute>,
    );

    expect(screen.getByText("Private product route")).toBeInTheDocument();
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("hides workspace content and redirects an unverified session to the pending page", async () => {
    mocks.useAuth.mockReturnValue({
      session: { ...session, emailVerified: false },
      isLoading: false,
    });

    render(
      <ProtectedRoute>
        <div>Private product route</div>
      </ProtectedRoute>,
    );

    expect(screen.queryByText("Private product route")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith("/verify-email/pending"),
    );
  });

  it("renders the pending page for an unverified session", () => {
    mocks.pathname = "/verify-email/pending";
    mocks.useAuth.mockReturnValue({
      session: { ...session, emailVerified: false },
      isLoading: false,
    });

    render(
      <ProtectedRoute>
        <div>Verification pending</div>
      </ProtectedRoute>,
    );

    expect(screen.getByText("Verification pending")).toBeInTheDocument();
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("hides the pending page and sends a verified session to the workspace", async () => {
    mocks.pathname = "/verify-email/pending";
    mocks.useAuth.mockReturnValue({ session, isLoading: false });

    render(
      <ProtectedRoute>
        <div>Verification pending</div>
      </ProtectedRoute>,
    );

    expect(screen.queryByText("Verification pending")).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/dashboard"));
  });

  it("redirects an authenticated user away from a guest route", async () => {
    mocks.useAuth.mockReturnValue({ session, isLoading: false });

    render(
      <GuestRoute>
        <div>Sign in form</div>
      </GuestRoute>,
    );

    expect(screen.queryByText("Sign in form")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith("/dashboard"),
    );
  });

  it("sends an unverified session from a guest route to the pending page", async () => {
    mocks.useAuth.mockReturnValue({
      session: { ...session, emailVerified: false },
      isLoading: false,
    });

    render(
      <GuestRoute>
        <div>Sign in form</div>
      </GuestRoute>,
    );

    expect(screen.queryByText("Sign in form")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith("/verify-email/pending"),
    );
  });

  it("keeps an invitation return path for a verified or unverified guest session", async () => {
    const next = "/invitations/accept?token=invite-token";
    window.history.replaceState({}, "", `/login?next=${encodeURIComponent(next)}`);
    mocks.useAuth.mockReturnValue({
      session: { ...session, emailVerified: false },
      isLoading: false,
    });

    render(
      <GuestRoute>
        <div>Sign in form</div>
      </GuestRoute>,
    );

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith(next));
    expect(mocks.replace).not.toHaveBeenCalledWith("/verify-email/pending");
    expect(mocks.replace).not.toHaveBeenCalledWith("/dashboard");
  });

  it("does not follow an external invitation return path", async () => {
    window.history.replaceState(
      {},
      "",
      "/login?next=https://evil.example/invitations/accept?token=x",
    );
    mocks.useAuth.mockReturnValue({ session, isLoading: false });

    render(
      <GuestRoute>
        <div>Sign in form</div>
      </GuestRoute>,
    );

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/dashboard"));
  });
});
