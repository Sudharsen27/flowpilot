import { describe, expect, it } from "vitest";

import {
  invitationReturnPath,
  loginPathForInvitation,
} from "@/lib/invitations/return-path";

describe("invitation return paths", () => {
  it("keeps only the accept page and its token", () => {
    expect(invitationReturnPath("/invitations/accept?token=abc")).toBe(
      "/invitations/accept?token=abc",
    );
    expect(invitationReturnPath("/invitations/accept?token=a%20b")).toBe(
      "/invitations/accept?token=a%20b",
    );
  });

  it("rejects other paths, extra parameters, and external urls", () => {
    expect(invitationReturnPath("/dashboard")).toBeNull();
    expect(invitationReturnPath("/invitations/accept")).toBeNull();
    expect(invitationReturnPath("/invitations/accept?token=abc&role=OWNER")).toBeNull();
    expect(invitationReturnPath("https://evil.example/invitations/accept?token=abc")).toBeNull();
    expect(invitationReturnPath("//evil.example/invitations/accept?token=abc")).toBeNull();
  });

  it("builds a login link without putting the token in storage", () => {
    expect(loginPathForInvitation("invite token")).toBe(
      `/login?next=${encodeURIComponent("/invitations/accept?token=invite%20token")}`,
    );
  });
});
