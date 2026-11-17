import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  leaveOrganization,
  listMembers,
  removeMember,
  transferOwnership,
  updateMemberRole,
} from "@/lib/api/members";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPatch: vi.fn(),
  apiDelete: vi.fn(),
  apiPost: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  apiGet: mocks.apiGet,
  apiPatch: mocks.apiPatch,
  apiDelete: mocks.apiDelete,
  apiPost: mocks.apiPost,
}));

describe("members api", () => {
  beforeEach(() => {
    mocks.apiGet.mockReset();
    mocks.apiPatch.mockReset();
    mocks.apiDelete.mockReset();
    mocks.apiPost.mockReset();
  });

  it("lists members", async () => {
    mocks.apiGet.mockResolvedValue([]);
    await expect(listMembers()).resolves.toEqual([]);
    expect(mocks.apiGet).toHaveBeenCalledWith("/api/v1/organizations/current/members");
  });

  it("updates a member role", async () => {
    mocks.apiPatch.mockResolvedValue({
      membership_id: "m-1",
      role: "ADMIN",
      user: { id: "u-1", name: "Ada", email: "ada@example.com" },
    });
    await updateMemberRole("m-1", "ADMIN");
    expect(mocks.apiPatch).toHaveBeenCalledWith(
      "/api/v1/organizations/current/members/m-1",
      { role: "ADMIN" },
    );
  });

  it("removes a member", async () => {
    mocks.apiDelete.mockResolvedValue(undefined);
    await removeMember("m-2");
    expect(mocks.apiDelete).toHaveBeenCalledWith(
      "/api/v1/organizations/current/members/m-2",
    );
  });

  it("leaves the organization", async () => {
    mocks.apiPost.mockResolvedValue(undefined);
    await expect(leaveOrganization()).resolves.toBeUndefined();
    expect(mocks.apiPost).toHaveBeenCalledWith("/api/v1/organizations/current/leave");
  });

  it("transfers ownership", async () => {
    mocks.apiPost.mockResolvedValue({
      membership_id: "m-3",
      role: "OWNER",
      user: { id: "u-3", name: "Bea", email: "bea@example.com" },
    });
    await transferOwnership("m-3");
    expect(mocks.apiPost).toHaveBeenCalledWith(
      "/api/v1/organizations/current/transfer-ownership",
      { membership_id: "m-3" },
    );
  });
});
