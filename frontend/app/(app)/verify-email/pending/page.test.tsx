import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import VerificationPendingPage from "@/app/(app)/verify-email/pending/page";

const ACCEPTED_MESSAGE =
  "If verification is available for this account, an email will be sent shortly.";

const mocks = vi.hoisted(() => ({
  requestVerificationEmail: vi.fn(),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    session: {
      user: {
        id: "user-1",
        email: "owner@example.com",
        name: "Owner",
      },
      organization: { id: "org-1", name: "Acme", slug: "acme" },
      membership: {
        id: "membership-1",
        organization_id: "org-1",
        user_id: "user-1",
        role: "OWNER",
      },
    },
  }),
}));

vi.mock("@/lib/api/auth", () => ({
  requestVerificationEmail: mocks.requestVerificationEmail,
}));

function resendButton() {
  return screen.getByRole("button", { name: /resend verification email/i });
}

describe("verification pending page", () => {
  beforeEach(() => {
    mocks.requestVerificationEmail.mockReset();
  });

  it("shows the signed-in email and a way into the workspace", () => {
    render(<VerificationPendingPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Verify your email" }),
    ).toBeVisible();
    expect(screen.getByText("Verification pending")).toBeVisible();
    expect(screen.getByText("owner@example.com")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Continue to workspace" }),
    ).toHaveAttribute("href", "/dashboard");
  });

  it("shows a generic accepted message after HTTP 200", async () => {
    const user = userEvent.setup();
    mocks.requestVerificationEmail.mockResolvedValue({ status: "accepted" });

    render(<VerificationPendingPage />);
    await user.click(resendButton());

    expect(mocks.requestVerificationEmail).toHaveBeenCalledWith(
      "owner@example.com",
    );
    expect(await screen.findByRole("status")).toHaveTextContent(ACCEPTED_MESSAGE);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a safe error and not the accepted message when the request fails", async () => {
    const user = userEvent.setup();
    mocks.requestVerificationEmail.mockRejectedValue(new Error("network"));

    render(<VerificationPendingPage />);
    await user.click(resendButton());

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The verification email could not be requested. Try again.",
    );
    expect(screen.queryByText(ACCEPTED_MESSAGE)).not.toBeInTheDocument();
    expect(resendButton()).toBeEnabled();
  });

  it("disables resend while the request is in progress and ignores a second click", async () => {
    let resolveRequest: (value: { status: "accepted" }) => void = () => {};
    mocks.requestVerificationEmail.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );

    render(<VerificationPendingPage />);
    const button = resendButton();
    await act(async () => {
      button.click();
      button.click();
    });

    expect(button).toBeDisabled();
    expect(button).toHaveTextContent("Sending…");
    expect(mocks.requestVerificationEmail).toHaveBeenCalledTimes(1);

    resolveRequest({ status: "accepted" });
    expect(await screen.findByRole("status")).toHaveTextContent(ACCEPTED_MESSAGE);
    expect(resendButton()).toBeEnabled();
  });
});
