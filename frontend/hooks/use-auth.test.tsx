import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "@/hooks/use-auth";
import type { AuthResponse, MeResponse } from "@/types/api";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiGet: mocks.apiGet,
  apiPost: mocks.apiPost,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace, refresh: mocks.refresh }),
}));

const me: MeResponse = {
  user: { id: "user-1", email: "owner@example.com", name: "Owner" },
  organization: { id: "org-1", name: "Acme", slug: "acme" },
  membership: {
    id: "membership-1",
    organization_id: "org-1",
    user_id: "user-1",
    role: "OWNER",
  },
};

const auth: AuthResponse = {
  ...me,
  access_token: "access-token",
  token_type: "bearer",
};

function AuthConsumer() {
  const { session, isLoading, signIn, signUp, signOut } = useAuth();

  if (isLoading) {
    return <span>Loading</span>;
  }

  return (
    <>
      <span>{session?.membership.role ?? "GUEST"}</span>
      <button
        type="button"
        onClick={() => void signIn("owner@example.com", "password12")}
      >
        Sign in
      </button>
      <button
        type="button"
        onClick={() =>
          void signUp({
            email: "owner@example.com",
            password: "password12",
            name: "Owner",
            organizationName: "Acme",
          })
        }
      >
        Register
      </button>
      <button type="button" onClick={signOut}>
        Sign out
      </button>
    </>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => {
    mocks.apiGet.mockReset();
    mocks.apiPost.mockReset();
    mocks.replace.mockReset();
    mocks.refresh.mockReset();
  });

  it("restores and preserves membership information", async () => {
    window.localStorage.setItem("flowpilot.access_token", "stored-token");
    mocks.apiGet.mockResolvedValue(me);

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );

    expect(await screen.findByText("OWNER")).toBeInTheDocument();
    expect(mocks.apiGet).toHaveBeenCalledWith("/api/v1/users/me");
  });

  it("keeps login and registration connected to their existing API endpoints", async () => {
    const user = userEvent.setup();
    mocks.apiPost.mockResolvedValue(auth);

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );
    await screen.findByText("GUEST");

    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() =>
      expect(mocks.apiPost).toHaveBeenCalledWith("/api/v1/auth/login", {
        email: "owner@example.com",
        password: "password12",
      }),
    );

    await user.click(screen.getByRole("button", { name: "Register" }));
    await waitFor(() =>
      expect(mocks.apiPost).toHaveBeenCalledWith("/api/v1/auth/register", {
        email: "owner@example.com",
        password: "password12",
        name: "Owner",
        organization_name: "Acme",
      }),
    );
  });

  it("clears session and token and redirects on logout", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("flowpilot.access_token", "stored-token");
    mocks.apiGet.mockResolvedValue(me);

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>,
    );
    await screen.findByText("OWNER");

    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(screen.getByText("GUEST")).toBeInTheDocument();
    expect(window.localStorage.getItem("flowpilot.access_token")).toBeNull();
    expect(mocks.replace).toHaveBeenCalledWith("/login");
    expect(mocks.refresh).toHaveBeenCalled();
  });
});
