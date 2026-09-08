import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GuestRoute } from "@/components/auth/guest-route";
import { ProtectedRoute } from "@/components/auth/protected-route";
import type { Session } from "@/hooks/use-auth";

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  useAuth: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace }),
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
};

describe("authentication route boundaries", () => {
  beforeEach(() => {
    mocks.replace.mockReset();
    mocks.useAuth.mockReset();
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

  it("redirects an authenticated user away from a guest route", async () => {
    mocks.useAuth.mockReturnValue({ session, isLoading: false });

    render(
      <GuestRoute>
        <div>Sign in form</div>
      </GuestRoute>,
    );

    expect(screen.queryByText("Sign in form")).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/"));
  });
});
