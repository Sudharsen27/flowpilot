import { describe, expect, it } from "vitest";

import {
  inboxUrlEquals,
  parseInboxSearchParams,
  serializeInboxSearchParams,
} from "@/lib/inbox-url";

describe("inbox URL helpers", () => {
  it("parses and serializes inbox search params", () => {
    const parsed = parseInboxSearchParams(
      new URLSearchParams(
        "q=Ada&state=NEEDS_APPROVAL&source=WEBSITE&needs_approval=true&offset=20&lead=lead-1",
      ),
    );
    expect(parsed).toEqual({
      q: "Ada",
      conversationState: "NEEDS_APPROVAL",
      source: "WEBSITE",
      needsApproval: "true",
      offset: 20,
      leadId: "lead-1",
    });
    expect(serializeInboxSearchParams(parsed)).toBe(
      "q=Ada&state=NEEDS_APPROVAL&source=WEBSITE&needs_approval=true&offset=20&lead=lead-1",
    );
  });

  it("ignores invalid enum values", () => {
    const parsed = parseInboxSearchParams(
      new URLSearchParams("state=NOPE&source=WHATSAPP&needs_approval=maybe"),
    );
    expect(parsed.conversationState).toBe("");
    expect(parsed.source).toBe("");
    expect(parsed.needsApproval).toBe("");
  });

  it("compares url state equality", () => {
    const base = parseInboxSearchParams(new URLSearchParams("q=a"));
    expect(inboxUrlEquals(base, { ...base })).toBe(true);
    expect(inboxUrlEquals(base, { ...base, q: "b" })).toBe(false);
  });
});
