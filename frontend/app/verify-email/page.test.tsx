import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import VerifyEmailPage from "@/app/verify-email/page";
import { ApiError } from "@/lib/api/client";

const state = vi.hoisted(() => ({
  token: "verify-token-secret-value",
  search: "token=verify-token-secret-value",
}));

const mocks = vi.hoisted(() => ({
  verifyEmail: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(state.search),
}));

vi.mock("@/lib/api/auth", () => ({
  verifyEmail: mocks.verifyEmail,
}));

describe("public email verification page", () => {
  beforeEach(() => {
    state.search = `token=${state.token}`;
    mocks.verifyEmail.mockReset();
    mocks.verifyEmail.mockResolvedValue({ status: "verified" });
  });

  it("submits a valid token once and does not display it", async () => {
    render(<VerifyEmailPage />);

    expect(screen.getByRole("status")).toHaveTextContent("Verifying your email…");
    await waitFor(() => expect(mocks.verifyEmail).toHaveBeenCalledTimes(1));
    expect(mocks.verifyEmail).toHaveBeenCalledWith(state.token);
    expect(document.body.textContent).not.toContain(state.token);
  });

  it("does not call the API when the token is missing", async () => {
    state.search = "";
    render(<VerifyEmailPage />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "This verification link is invalid or has expired.",
    );
    await waitFor(() => expect(mocks.verifyEmail).not.toHaveBeenCalled());
  });

  it("does not call the API when the token is empty", async () => {
    state.search = "token=";
    render(<VerifyEmailPage />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "This verification link is invalid or has expired.",
    );
    await waitFor(() => expect(mocks.verifyEmail).not.toHaveBeenCalled());
  });

  it("shows the verified state after HTTP 200", async () => {
    render(<VerifyEmailPage />);

    expect(await screen.findByText("Your email is verified.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Continue to workspace" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(document.body.textContent).not.toContain(state.token);
  });

  it("shows an invalid or expired link after HTTP 400", async () => {
    mocks.verifyEmail.mockRejectedValue(
      new ApiError("Request failed: 400", 400, { detail: state.token }),
    );
    render(<VerifyEmailPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This verification link is invalid or has expired.",
    );
    expect(document.body.textContent).not.toContain(state.token);
    expect(mocks.verifyEmail).toHaveBeenCalledTimes(1);
  });

  it("shows a rate-limit message after HTTP 429", async () => {
    mocks.verifyEmail.mockRejectedValue(new ApiError("Request failed: 429", 429));
    render(<VerifyEmailPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many attempts. Try again later.",
    );
    expect(mocks.verifyEmail).toHaveBeenCalledTimes(1);
  });

  it("shows a safe validation message after HTTP 422", async () => {
    mocks.verifyEmail.mockRejectedValue(
      new ApiError("Request failed: 422", 422, { detail: state.token }),
    );
    render(<VerifyEmailPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This verification link could not be accepted.",
    );
    expect(document.body.textContent).not.toContain(state.token);
  });

  it("shows a generic error for an unexpected failure and does not retry", async () => {
    mocks.verifyEmail.mockRejectedValue(new Error("network"));
    render(<VerifyEmailPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email verification could not be completed. Try again later.",
    );
    await waitFor(() => expect(mocks.verifyEmail).toHaveBeenCalledTimes(1));
  });
});
