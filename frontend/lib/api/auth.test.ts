import { beforeEach, describe, expect, it, vi } from "vitest";

import { requestVerificationEmail, verifyEmail } from "@/lib/api/auth";

const mocks = vi.hoisted(() => ({
  apiPost: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiPost: mocks.apiPost,
}));

describe("requestVerificationEmail", () => {
  beforeEach(() => {
    mocks.apiPost.mockReset();
  });

  it("posts the email to the verification-email endpoint", async () => {
    mocks.apiPost.mockResolvedValue({ status: "accepted" });

    await expect(requestVerificationEmail("owner@example.com")).resolves.toEqual({
      status: "accepted",
    });
    expect(mocks.apiPost).toHaveBeenCalledWith(
      "/api/v1/auth/verification-email",
      { email: "owner@example.com" },
    );
  });

  it("posts the verification token without a session", async () => {
    mocks.apiPost.mockResolvedValue({ status: "verified" });

    await expect(verifyEmail("raw-token")).resolves.toEqual({ status: "verified" });
    expect(mocks.apiPost).toHaveBeenCalledWith(
      "/api/v1/auth/verify-email",
      { token: "raw-token" },
      { token: null },
    );
  });
});
