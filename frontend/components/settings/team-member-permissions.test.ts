import { describe, expect, it } from "vitest";

import {
  assignableRolesFor,
  canChangeMemberRole,
  canLeaveOrganization,
  canRemoveMember,
} from "@/components/settings/team-member-permissions";

describe("team member permissions", () => {
  it("lets owners change admin and member roles but not the owner", () => {
    expect(assignableRolesFor("OWNER", "ADMIN")).toEqual(["ADMIN", "MEMBER"]);
    expect(assignableRolesFor("OWNER", "MEMBER")).toEqual(["ADMIN", "MEMBER"]);
    expect(assignableRolesFor("OWNER", "OWNER")).toEqual([]);
    expect(canChangeMemberRole("OWNER", "ADMIN")).toBe(true);
    expect(canChangeMemberRole("OWNER", "OWNER")).toBe(false);
  });

  it("blocks admins from promoting or touching admins", () => {
    expect(assignableRolesFor("ADMIN", "MEMBER")).toEqual(["MEMBER"]);
    expect(canChangeMemberRole("ADMIN", "MEMBER")).toBe(false);
    expect(canChangeMemberRole("ADMIN", "ADMIN")).toBe(false);
    expect(canChangeMemberRole("MEMBER", "MEMBER")).toBe(false);
  });

  it("enforces remove and leave rules", () => {
    expect(canRemoveMember("OWNER", "ADMIN", false)).toBe(true);
    expect(canRemoveMember("OWNER", "OWNER", false)).toBe(false);
    expect(canRemoveMember("OWNER", "MEMBER", true)).toBe(false);
    expect(canRemoveMember("ADMIN", "MEMBER", false)).toBe(true);
    expect(canRemoveMember("ADMIN", "ADMIN", false)).toBe(false);
    expect(canRemoveMember("MEMBER", "MEMBER", false)).toBe(false);
    expect(canLeaveOrganization("OWNER")).toBe(false);
    expect(canLeaveOrganization("ADMIN")).toBe(true);
    expect(canLeaveOrganization("MEMBER")).toBe(true);
  });
});
