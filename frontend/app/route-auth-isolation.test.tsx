import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AuthLayout from "@/app/(auth)/layout";
import WorkspaceLayout from "@/app/(app)/layout";
import MarketingLayout from "@/app/(marketing)/layout";
import RootLayout from "@/app/layout";
import { useAuth } from "@/hooks/use-auth";
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

vi.mock("next/font/google", () => ({
  Geist: () => ({ variable: "" }),
  Geist_Mono: () => ({ variable: "" }),
}));

vi.mock("next/script", () => ({ default: () => null }));

vi.mock("@/components/app-shell", async () => {
  const React = await import("react");
  const { useAuth: readSession } = await import("@/hooks/use-auth");

  return {
    AppShell: ({ children }: { children: ReactNode }) => {
      const { session } = readSession();
      return React.createElement(
        "div",
        null,
        React.createElement("span", null, session?.organization.name ?? "No organization"),
        children,
      );
    },
  };
});

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
  access_token: "new-access-token",
  token_type: "bearer",
};

function AuthPageProbe() {
  const { session, isLoading, signIn, signUp } = useAuth();

  if (isLoading) return <p>Loading authentication</p>;

  return (
    <>
      <p>{session?.organization.name ?? "Guest auth page"}</p>
      <button type="button" onClick={() => void signIn("owner@example.com", "password12")}>
        Login
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
    </>
  );
}

describe("route-group authentication providers", () => {
  beforeEach(() => {
    mocks.apiGet.mockReset();
    mocks.apiPost.mockReset();
    mocks.replace.mockReset();
    mocks.refresh.mockReset();
  });

  it.each([false, true])(
    "renders public marketing without restoring auth when a token exists: %s",
    async (hasStoredToken) => {
      if (hasStoredToken) {
        window.localStorage.setItem("flowpilot.access_token", "stored-token");
      }
      mocks.apiGet.mockResolvedValue(me);

      render(
        <RootLayout>
          <MarketingLayout>
            <main>Public marketing content</main>
          </MarketingLayout>
        </RootLayout>,
      );

      expect(await screen.findByText("Public marketing content")).toBeVisible();
      expect(mocks.apiGet).not.toHaveBeenCalled();
    },
  );

  it("keeps guest auth pages provider-backed and login/register connected", async () => {
    const user = userEvent.setup();
    mocks.apiPost.mockResolvedValue(auth);

    render(
      <AuthLayout>
        <AuthPageProbe />
      </AuthLayout>,
    );

    expect(await screen.findByText("Guest auth page")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Login" }));
    await waitFor(() =>
      expect(mocks.apiPost).toHaveBeenCalledWith("/api/v1/auth/login", {
        email: "owner@example.com",
        password: "password12",
      }),
    );
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/dashboard"));

    mocks.apiPost.mockClear();
    mocks.replace.mockClear();
    window.localStorage.clear();
    render(
      <AuthLayout>
        <AuthPageProbe />
      </AuthLayout>,
    );
    expect(await screen.findByText("Guest auth page")).toBeVisible();
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

  it("restores workspace organization context for authenticated routes", async () => {
    window.localStorage.setItem("flowpilot.access_token", "stored-token");
    mocks.apiGet.mockResolvedValue(me);

    render(
      <WorkspaceLayout>
        <p>Protected workspace content</p>
      </WorkspaceLayout>,
    );

    expect(await screen.findByText("Acme")).toBeVisible();
    expect(screen.getByText("Protected workspace content")).toBeVisible();
    expect(mocks.apiGet).toHaveBeenCalledWith("/api/v1/users/me");
  });

  it("keeps protected workspace content hidden and redirects signed-out users", async () => {
    render(
      <WorkspaceLayout>
        <p>Private workspace content</p>
      </WorkspaceLayout>,
    );

    expect(screen.queryByText("Private workspace content")).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/login"));
  });

  it("redirects authenticated users away from guest auth pages", async () => {
    window.localStorage.setItem("flowpilot.access_token", "stored-token");
    mocks.apiGet.mockResolvedValue(me);

    render(
      <AuthLayout>
        <p>Guest-only content</p>
      </AuthLayout>,
    );

    expect(screen.queryByText("Guest-only content")).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/dashboard"));
  });
});