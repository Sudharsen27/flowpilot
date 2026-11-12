import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ResetPasswordPage from "@/app/reset-password/page";
import { ApiError } from "@/lib/api/client";

const state = vi.hoisted(() => ({
  token: "reset-token-secret-value",
  search: "token=reset-token-secret-value",
}));

const mocks = vi.hoisted(() => ({
  confirmPasswordReset: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(state.search),
}));

vi.mock("@/lib/api/auth", () => ({
  confirmPasswordReset: mocks.confirmPasswordReset,
}));

const PASSWORD = "new-password-34";

async function fillPasswords(
  user: ReturnType<typeof userEvent.setup>,
  password = PASSWORD,
  confirmation = PASSWORD,
) {
  await user.type(screen.getByLabelText(/^new password/i), password);
  await user.type(screen.getByLabelText(/^confirm new password/i), confirmation);
}

describe("public password reset page", () => {
  beforeEach(() => {
    state.search = `token=${state.token}`;
    mocks.confirmPasswordReset.mockReset();
    mocks.confirmPasswordReset.mockResolvedValue({ status: "reset" });
  });

  it("does not call the API when the token is missing or blank", async () => {
    state.search = "";
    const { unmount } = render(<ResetPasswordPage />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This password reset link is invalid or has expired.",
    );
    expect(screen.queryByLabelText(/^new password/i)).not.toBeInTheDocument();

    unmount();
    state.search = "token=";
    render(<ResetPasswordPage />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "This password reset link is invalid or has expired.",
    );
    expect(mocks.confirmPasswordReset).not.toHaveBeenCalled();
    expect(document.body.innerHTML).not.toContain(state.token);
  });

  it("rejects a short password and a confirmation mismatch before calling the API", async () => {
    const user = userEvent.setup();
    render(<ResetPasswordPage />);

    await fillPasswords(user, "short", "short");
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Use at least 8 characters.");
    expect(mocks.confirmPasswordReset).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText(/^new password/i));
    await user.clear(screen.getByLabelText(/^confirm new password/i));
    await fillPasswords(user, PASSWORD, "different-password");
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Passwords do not match.");
    expect(mocks.confirmPasswordReset).not.toHaveBeenCalled();
  });

  it("submits the token and password once and shows the sign-in link", async () => {
    const user = userEvent.setup();
    const log = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const info = vi.spyOn(console, "info").mockImplementation(() => undefined);
    const debug = vi.spyOn(console, "debug").mockImplementation(() => undefined);
    render(<ResetPasswordPage />);

    await fillPasswords(user);
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(await screen.findByText("Your password has been reset.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(mocks.confirmPasswordReset).toHaveBeenCalledTimes(1);
    expect(mocks.confirmPasswordReset).toHaveBeenCalledWith(state.token, PASSWORD);
    expect(document.body.innerHTML).not.toContain(state.token);
    expect(log.mock.calls.flat().join(" ")).not.toContain(state.token);
    expect(info.mock.calls.flat().join(" ")).not.toContain(state.token);
    expect(debug.mock.calls.flat().join(" ")).not.toContain(state.token);
    log.mockRestore();
    info.mockRestore();
    debug.mockRestore();
  });

  it("shows an invalid link, a validation error, and a rate limit without the token", async () => {
    const user = userEvent.setup();
    mocks.confirmPasswordReset.mockRejectedValue(
      new ApiError("Request failed: 400", 400, { detail: state.token }),
    );
    const { unmount } = render(<ResetPasswordPage />);
    await fillPasswords(user);
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This password reset link is invalid or has expired.",
    );
    expect(document.body.innerHTML).not.toContain(state.token);

    unmount();
    mocks.confirmPasswordReset.mockRejectedValue(
      new ApiError("Request failed: 422", 422, { detail: state.token }),
    );
    const second = render(<ResetPasswordPage />);
    await fillPasswords(user);
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This password could not be accepted.",
    );
    expect(document.body.innerHTML).not.toContain(state.token);

    second.unmount();
    mocks.confirmPasswordReset.mockRejectedValue(new ApiError("Request failed: 429", 429));
    render(<ResetPasswordPage />);
    await fillPasswords(user);
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Too many attempts. Try again later.",
    );
    expect(mocks.confirmPasswordReset).toHaveBeenCalledTimes(3);
  });

  it("shows a retryable error after a network failure and does not retry", async () => {
    const user = userEvent.setup();
    mocks.confirmPasswordReset.mockRejectedValue(new Error("network"));
    render(<ResetPasswordPage />);
    await fillPasswords(user);
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The password could not be reset. Try again.",
    );
    expect(screen.getByRole("button", { name: "Reset password" })).toBeEnabled();
    expect(mocks.confirmPasswordReset).toHaveBeenCalledTimes(1);
  });

  it("does not send a second reset while the first is running", async () => {
    let resolveRequest: (value: { status: "reset" }) => void = () => {};
    mocks.confirmPasswordReset.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );
    const user = userEvent.setup();
    render(<ResetPasswordPage />);
    await fillPasswords(user);
    const button = screen.getByRole("button", { name: "Reset password" });
    await act(async () => {
      button.click();
      button.click();
    });

    expect(button).toBeDisabled();
    expect(mocks.confirmPasswordReset).toHaveBeenCalledTimes(1);

    resolveRequest({ status: "reset" });
    expect(await screen.findByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
  });
});
