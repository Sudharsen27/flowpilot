import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/(auth)/login/page";
import RegisterPage from "@/app/(auth)/register/page";
import { ApiError } from "@/lib/api/client";
import type { AuthResponse } from "@/types/api";

const auth: AuthResponse = {
  access_token: "access-token",
  token_type: "bearer",
  user: { id: "user-1", email: "owner@example.com", name: "Owner" },
  organization: { id: "org-1", name: "Acme", slug: "acme" },
  membership: {
    id: "membership-1",
    organization_id: "org-1",
    user_id: "user-1",
    role: "OWNER",
  },
};

const ACCEPTED_MESSAGE =
  "If verification is available for this account, an email will be sent shortly.";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  signIn: vi.fn(),
  signUp: vi.fn(),
  completeAuth: vi.fn(),
  requestVerificationEmail: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api/auth", () => ({
  requestVerificationEmail: mocks.requestVerificationEmail,
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    signIn: mocks.signIn,
    signUp: mocks.signUp,
    completeAuth: mocks.completeAuth,
  }),
}));

vi.mock("@/components/auth/google-continue-button", () => ({
  GoogleContinueButton: ({
    onSuccess,
  }: {
    onSuccess: (auth: AuthResponse) => void;
    onError: (message: string) => void;
  }) => (
    <button type="button" onClick={() => onSuccess(auth)}>
      Continue with Google
    </button>
  ),
  AuthDivider: () => <hr />,
}));

describe("auth pages", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.signIn.mockReset();
    mocks.signUp.mockReset();
    mocks.completeAuth.mockReset();
    mocks.requestVerificationEmail.mockReset();
  });

  it("frames sign-in as an approval workspace", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
    expect(
      screen.getByRole("heading", {
        name: "One company workspace from the enquiry to the approved reply.",
      }),
    ).toBeVisible();
    expect(screen.getByText("Organization")).toBeVisible();
    expect(screen.getByText("Preparation")).toBeVisible();
    expect(screen.getByText("Control")).toBeVisible();
    expect(screen.getByText("Example. Approval does not send the email.")).toBeVisible();
    expect(screen.getByText("Example")).toBeVisible();
    expect(screen.getByRole("link", { name: "Create an account" })).toHaveAttribute(
      "href",
      "/register",
    );
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  it("creates an organization without calling the form a development stub", () => {
    render(<RegisterPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Create account" })).toBeVisible();
    expect(screen.getByText(/owner membership/)).toBeVisible();
    expect(screen.queryByText(/development sign-up/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Create account" })).toBeVisible();
  });

  it("keeps the session and opens the verification pending page after password registration", async () => {
    const user = userEvent.setup();
    mocks.signUp.mockResolvedValue(undefined);

    render(<RegisterPage />);
    await user.type(screen.getByLabelText(/your name/i), "Owner");
    await user.type(screen.getByLabelText(/organization name/i), "Acme");
    await user.type(screen.getByLabelText(/^email/i), "owner@example.com");
    await user.type(screen.getByLabelText(/^password/i), "password12");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(mocks.signUp).toHaveBeenCalledWith({
      email: "owner@example.com",
      password: "password12",
      name: "Owner",
      organizationName: "Acme",
    });
    expect(mocks.push).toHaveBeenCalledWith("/verify-email/pending");
    expect(mocks.push).not.toHaveBeenCalledWith("/dashboard");
  });

  it("opens the workspace after Google registration", async () => {
    const user = userEvent.setup();

    render(<RegisterPage />);
    await user.click(screen.getByRole("button", { name: "Continue with Google" }));

    expect(mocks.completeAuth).toHaveBeenCalledWith(auth);
    expect(mocks.push).toHaveBeenCalledWith("/dashboard");
  });

  it("keeps the existing conflict message when registration returns HTTP 409", async () => {
    const user = userEvent.setup();
    mocks.signUp.mockRejectedValue(new ApiError("Request failed: 409", 409));

    render(<RegisterPage />);
    await user.type(screen.getByLabelText(/your name/i), "Owner");
    await user.type(screen.getByLabelText(/organization name/i), "Acme");
    await user.type(screen.getByLabelText(/^email/i), "owner@example.com");
    await user.type(screen.getByLabelText(/^password/i), "password12");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That email is already registered.",
    );
    expect(mocks.push).not.toHaveBeenCalled();
  });

  async function fillLogin(user: ReturnType<typeof userEvent.setup>) {
    render(<LoginPage />);
    await user.type(screen.getByLabelText(/^email/i), "owner@example.com");
    await user.type(screen.getByLabelText(/^password/i), "password12");
  }

  it("opens the workspace after a successful login", async () => {
    const user = userEvent.setup();
    mocks.signIn.mockResolvedValue(undefined);

    await fillLogin(user);
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(mocks.signIn).toHaveBeenCalledWith("owner@example.com", "password12");
    expect(mocks.push).toHaveBeenCalledWith("/dashboard");
  });

  it("keeps invalid credentials and too many attempts distinct", async () => {
    const user = userEvent.setup();
    mocks.signIn.mockRejectedValue(new ApiError("Request failed: 401", 401));

    await fillLogin(user);
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid email or password.",
    );
    expect(mocks.push).not.toHaveBeenCalled();

    mocks.signIn.mockRejectedValue(new ApiError("Request failed: 429", 429));
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many attempts. Try again later.",
    );
    expect(mocks.push).not.toHaveBeenCalled();
  });

  it("requests a verification email for the entered address without signing in", async () => {
    const user = userEvent.setup();
    mocks.requestVerificationEmail.mockResolvedValue({ status: "accepted" });

    render(<LoginPage />);
    await user.type(screen.getByLabelText(/^email/i), "owner@example.com");
    await user.click(screen.getByRole("button", { name: "Resend verification email" }));

    expect(mocks.requestVerificationEmail).toHaveBeenCalledWith("owner@example.com");
    expect(mocks.signIn).not.toHaveBeenCalled();
    expect(mocks.push).not.toHaveBeenCalled();
    expect(await screen.findByRole("status")).toHaveTextContent(ACCEPTED_MESSAGE);
  });

  it("shows a retryable error when the verification request fails", async () => {
    const user = userEvent.setup();
    mocks.requestVerificationEmail.mockRejectedValue(new Error("network"));

    render(<LoginPage />);
    await user.type(screen.getByLabelText(/^email/i), "owner@example.com");
    await user.click(screen.getByRole("button", { name: "Resend verification email" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The verification email could not be requested. Try again.",
    );
    expect(screen.queryByText(ACCEPTED_MESSAGE)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resend verification email" })).toBeEnabled();
  });

  it("does not send a second verification request while the first is running", async () => {
    let resolveRequest: (value: { status: "accepted" }) => void = () => {};
    mocks.requestVerificationEmail.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );

    render(<LoginPage />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/^email/i), "owner@example.com");
    const button = screen.getByRole("button", { name: "Resend verification email" });
    await act(async () => {
      button.click();
      button.click();
    });

    expect(button).toBeDisabled();
    expect(mocks.requestVerificationEmail).toHaveBeenCalledTimes(1);

    resolveRequest({ status: "accepted" });
    expect(await screen.findByRole("status")).toHaveTextContent(ACCEPTED_MESSAGE);
  });
});
