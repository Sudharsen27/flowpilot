import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GoogleContinueButton } from "@/components/auth/google-continue-button";
import { ApiError, apiPost } from "@/lib/api/client";
import type { AuthResponse } from "@/types/api";

vi.mock("@/lib/api/client", () => {
  class MockApiError extends Error {
    readonly status: number;
    readonly body: unknown;
    constructor(message: string, status: number, body: unknown = null) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.body = body;
    }
  }
  return {
    apiPost: vi.fn(),
    ApiError: MockApiError,
  };
});

const apiPostMock = vi.mocked(apiPost);

type GoogleCallback = (response: { code?: string; error?: string }) => void;

const auth = {
  access_token: "token",
  token_type: "bearer",
  user: { id: "user-1", email: "ada@example.com", name: "Ada" },
  organization: {
    id: "org-1",
    name: "Ada Org",
    slug: "ada-org",
    website_capture_enabled: false,
    default_currency: "INR",
  },
  membership: {
    id: "membership-1",
    role: "OWNER",
    organization_id: "org-1",
    user_id: "user-1",
  },
} as AuthResponse;

function installGoogle() {
  let callback: GoogleCallback = () => undefined;
  const requestCode = vi.fn();
  window.google = {
    accounts: {
      oauth2: {
        initCodeClient: (config) => {
          callback = config.callback;
          return { requestCode };
        },
      },
    },
  };
  return {
    requestCode,
    respond: (response: { code?: string; error?: string }) => callback(response),
  };
}

async function renderReady() {
  vi.stubEnv("NEXT_PUBLIC_GOOGLE_CLIENT_ID", "test-client-id");
  const google = installGoogle();
  const onSuccess = vi.fn();
  const onError = vi.fn();
  const view = render(<GoogleContinueButton onSuccess={onSuccess} onError={onError} />);
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeEnabled(),
  );
  return { ...google, onSuccess, onError, user: userEvent.setup(), unmount: view.unmount };
}

describe("GoogleContinueButton", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
    delete window.google;
  });

  it("shows a clear error when the Google client id is missing", async () => {
    vi.stubEnv("NEXT_PUBLIC_GOOGLE_CLIENT_ID", "");
    const onSuccess = vi.fn();
    const onError = vi.fn();
    const user = userEvent.setup();

    render(<GoogleContinueButton onSuccess={onSuccess} onError={onError} />);

    await user.click(screen.getByRole("button", { name: "Continue with Google" }));

    expect(onError).toHaveBeenCalledWith("Google sign-in is not configured.");
    expect(onSuccess).not.toHaveBeenCalled();
    expect(screen.queryByLabelText(/Existing FlowPilot password/)).not.toBeInTheDocument();
  });

  it("signs in with the authorization code and does not ask for a password", async () => {
    apiPostMock.mockResolvedValue(auth);
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "fresh-code" });

    await waitFor(() => expect(view.onSuccess).toHaveBeenCalledWith(auth));
    expect(apiPostMock).toHaveBeenCalledWith(
      "/api/v1/auth/google",
      { code: "fresh-code" },
      { token: null },
    );
    expect(screen.queryByLabelText(/Existing FlowPilot password/)).not.toBeInTheDocument();
  });

  it("asks for the existing password after a 401 without calling it incorrect", async () => {
    apiPostMock.mockRejectedValue(new ApiError("Request failed: 401", 401));
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "spent-code" });

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/existing FlowPilot password/i);
    expect(alert).not.toHaveTextContent(/incorrect|wrong password/i);
    expect(screen.getByLabelText(/Existing FlowPilot password/)).toHaveAttribute(
      "id",
      "google-link-password",
    );
    expect(view.onSuccess).not.toHaveBeenCalled();
    expect(view.onError).not.toHaveBeenCalledWith("Unable to continue with Google.");
  });

  it("does not ask for a password on a 502", async () => {
    apiPostMock.mockRejectedValue(new ApiError("Request failed: 502", 502));
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "provider-code" });

    await waitFor(() =>
      expect(view.onError).toHaveBeenCalledWith("Unable to continue with Google."),
    );
    expect(screen.queryByLabelText(/Existing FlowPilot password/)).not.toBeInTheDocument();
  });

  it("does not ask for a password when Google sign-in is not configured", async () => {
    apiPostMock.mockRejectedValue(new ApiError("Request failed: 503", 503));
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "unavailable-code" });

    await waitFor(() =>
      expect(view.onError).toHaveBeenCalledWith("Google sign-in is not configured."),
    );
    expect(screen.queryByLabelText(/Existing FlowPilot password/)).not.toBeInTheDocument();
  });

  it("sends a fresh code with the password and clears it after success", async () => {
    apiPostMock
      .mockRejectedValueOnce(new ApiError("Request failed: 401", 401))
      .mockResolvedValueOnce(auth);
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "first-code" });
    const field = await screen.findByLabelText(/Existing FlowPilot password/);
    await view.user.type(field, "password12");
    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "second-code" });

    await waitFor(() => expect(view.onSuccess).toHaveBeenCalledWith(auth));
    expect(apiPostMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/auth/google",
      { code: "first-code" },
      { token: null },
    );
    expect(apiPostMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/auth/google",
      { code: "second-code", password: "password12" },
      { token: null },
    );
    expect(apiPostMock.mock.calls[1]?.[1]).not.toMatchObject({ code: "first-code" });
    expect(screen.queryByLabelText(/Existing FlowPilot password/)).not.toBeInTheDocument();

    apiPostMock.mockResolvedValueOnce(auth);
    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "third-code" });
    await waitFor(() => expect(apiPostMock).toHaveBeenCalledTimes(3));
    expect(apiPostMock).toHaveBeenLastCalledWith(
      "/api/v1/auth/google",
      { code: "third-code" },
      { token: null },
    );
  });

  it("clears the password and stays neutral when the second attempt returns 401", async () => {
    apiPostMock.mockRejectedValue(new ApiError("Request failed: 401", 401));
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "first-code" });
    const field = await screen.findByLabelText(/Existing FlowPilot password/);
    await view.user.type(field, "not-the-password");
    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "second-code" });

    const alert = await screen.findByRole("alert");
    await waitFor(() =>
      expect(alert).toHaveTextContent(/could not connect this Google account/i),
    );
    expect(alert).toHaveTextContent(/sign in with email and password/i);
    expect(alert).not.toHaveTextContent(/incorrect|wrong password/i);
    expect(screen.getByLabelText(/Existing FlowPilot password/)).toHaveValue("");
    expect(view.onSuccess).not.toHaveBeenCalled();
    expect(apiPostMock).toHaveBeenLastCalledWith(
      "/api/v1/auth/google",
      { code: "second-code", password: "not-the-password" },
      { token: null },
    );
  });

  it("keeps 400 and 409 failures on the existing Google error", async () => {
    for (const status of [400, 409]) {
      apiPostMock.mockRejectedValue(new ApiError(`Request failed: ${status}`, status));
      const view = await renderReady();
      await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
      view.respond({ code: `code-${status}` });
      await waitFor(() =>
        expect(view.onError).toHaveBeenCalledWith("Unable to continue with Google."),
      );
      expect(screen.queryByLabelText(/Existing FlowPilot password/)).not.toBeInTheDocument();
      cleanup();
    }
  });

  it("does not open another Google prompt until a password is entered", async () => {
    apiPostMock.mockRejectedValue(new ApiError("Request failed: 401", 401));
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "spent-code" });
    await screen.findByLabelText(/Existing FlowPilot password/);
    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));

    expect(view.requestCode).toHaveBeenCalledTimes(1);
    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Enter the existing FlowPilot password/i,
    );
  });

  it("does not start a second Google prompt while a request is in progress", async () => {
    let resolveRequest: (value: AuthResponse) => void = () => undefined;
    apiPostMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    expect(view.requestCode).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Continuing…" })).toBeDisabled();

    view.respond({ code: "in-flight-code" });
    await waitFor(() => expect(apiPostMock).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "Continuing…" })).toBeDisabled();
    expect(view.requestCode).toHaveBeenCalledTimes(1);

    resolveRequest(auth);
    await waitFor(() => expect(view.onSuccess).toHaveBeenCalledWith(auth));
  });

  it("drops the entered password when the button unmounts", async () => {
    apiPostMock.mockRejectedValue(new ApiError("Request failed: 401", 401));
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "spent-code" });
    const field = await screen.findByLabelText(/Existing FlowPilot password/);
    await view.user.type(field, "password12");
    expect(field).toHaveValue("password12");
    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.unmount();
    view.respond({ code: "late-code" });

    await Promise.resolve();
    expect(screen.queryByLabelText(/Existing FlowPilot password/)).not.toBeInTheDocument();
    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(apiPostMock).toHaveBeenCalledWith(
      "/api/v1/auth/google",
      { code: "spent-code" },
      { token: null },
    );
    expect(JSON.stringify(apiPostMock.mock.calls)).not.toContain("password12");
    expect(view.onSuccess).not.toHaveBeenCalled();
    expect(view.onError).not.toHaveBeenCalledWith("Unable to continue with Google.");
  });

  it("does not submit a Google callback that arrives after unmount", async () => {
    apiPostMock.mockRejectedValue(new ApiError("Request failed: 401", 401));
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "spent-code" });
    const field = await screen.findByLabelText(/Existing FlowPilot password/);
    await view.user.type(field, "password12");
    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.unmount();
    view.respond({ code: "late-code" });

    await Promise.resolve();
    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(apiPostMock).toHaveBeenCalledWith(
      "/api/v1/auth/google",
      { code: "spent-code" },
      { token: null },
    );
    expect(view.onSuccess).not.toHaveBeenCalled();
  });

  it("processes one authorization response only once", async () => {
    apiPostMock.mockResolvedValue(auth);
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "only-once" });
    view.respond({ code: "duplicate-delivery" });

    await waitFor(() => expect(view.onSuccess).toHaveBeenCalledTimes(1));
    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(apiPostMock).toHaveBeenCalledWith(
      "/api/v1/auth/google",
      { code: "only-once" },
      { token: null },
    );
  });

  it("accepts a fresh popup after a failed request", async () => {
    apiPostMock
      .mockRejectedValueOnce(new ApiError("Request failed: 502", 502))
      .mockResolvedValueOnce(auth);
    const view = await renderReady();

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "failed-code" });
    view.respond({ code: "duplicate-of-failed-code" });

    await waitFor(() =>
      expect(view.onError).toHaveBeenCalledWith("Unable to continue with Google."),
    );
    expect(apiPostMock).toHaveBeenCalledTimes(1);

    await view.user.click(screen.getByRole("button", { name: "Continue with Google" }));
    view.respond({ code: "fresh-code" });

    await waitFor(() => expect(view.onSuccess).toHaveBeenCalledWith(auth));
    expect(apiPostMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/auth/google",
      { code: "fresh-code" },
      { token: null },
    );
  });
});
