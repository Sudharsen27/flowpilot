import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GoogleContinueButton } from "@/components/auth/google-continue-button";

describe("GoogleContinueButton", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
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
  });
});
