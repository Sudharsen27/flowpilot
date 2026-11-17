import { describe, expect, it } from "vitest";

import {
  hasActivityFilters,
  parseActivitySearchParams,
  serializeActivitySearchParams,
} from "@/lib/activity-url";

describe("activity url helpers", () => {
  it("parses and serializes filters and selection", () => {
    const parsed = parseActivitySearchParams(
      new URLSearchParams(
        "q=hello&type=AI_ACTION&entity_type=LEAD&offset=20&event=event-1",
      ),
    );
    expect(parsed).toEqual({
      q: "hello",
      type: "AI_ACTION",
      entityType: "LEAD",
      offset: 20,
      eventId: "event-1",
    });
    expect(serializeActivitySearchParams(parsed)).toBe(
      "q=hello&type=AI_ACTION&entity_type=LEAD&offset=20&event=event-1",
    );
  });

  it("drops invalid filter values", () => {
    const parsed = parseActivitySearchParams(
      new URLSearchParams("type=NOPE&entity_type=BAD&offset=-1&event="),
    );
    expect(parsed).toEqual({
      q: "",
      type: "",
      entityType: "",
      offset: 0,
      eventId: null,
    });
    expect(hasActivityFilters(parsed)).toBe(false);
  });
});
