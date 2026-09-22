import { describe, expect, it } from "vitest";

import {
  buildApprovalsHref,
  parseApprovalsSearchParams,
  serializeApprovalsSearchParams,
} from "@/lib/approvals-url";

describe("approvals-url", () => {
  it("serializes pending queue without query when defaults apply", () => {
    expect(
      serializeApprovalsSearchParams({
        q: "",
        status: "pending",
        offset: 0,
        approvalId: null,
      }),
    ).toBe("");
  });

  it("builds Approval Center root for pending handoff", () => {
    expect(buildApprovalsHref()).toBe("/approvals");
    expect(buildApprovalsHref({ approvalId: null })).toBe("/approvals");
    expect(buildApprovalsHref({ approvalId: "   " })).toBe("/approvals");
  });

  it("builds selected approval href using draft_id as approval param", () => {
    expect(buildApprovalsHref({ approvalId: "draft-1" })).toBe(
      "/approvals?approval=draft-1",
    );
    expect(
      parseApprovalsSearchParams(
        new URLSearchParams("approval=draft-1"),
      ).approvalId,
    ).toBe("draft-1");
  });

  it("includes non-default status when selecting an approval", () => {
    expect(
      buildApprovalsHref({ approvalId: "draft-1", status: "approved" }),
    ).toBe("/approvals?status=approved&approval=draft-1");
  });
});
