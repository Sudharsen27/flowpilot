import { describe, expect, it } from "vitest";

import {
  formatAbsoluteTimestamp,
  formatRelativeTimestamp,
} from "@/lib/datetime";

describe("datetime helpers", () => {
  const now = new Date("2026-09-22T12:00:00Z");

  it("formats absolute timestamps", () => {
    expect(formatAbsoluteTimestamp("2026-09-22T12:00:00Z")).toBe(
      "2026-09-22 12:00:00 UTC",
    );
    expect(formatAbsoluteTimestamp(null)).toBeNull();
  });

  it("normalizes offset and fractional-second timestamps to UTC", () => {
    expect(formatAbsoluteTimestamp("2026-09-25 12:31:24.220271+05:30")).toBe(
      "2026-09-25 07:01:24 UTC",
    );
    expect(formatAbsoluteTimestamp("not a date")).toBe("not a date");
  });

  it("formats relative timestamps", () => {
    expect(formatRelativeTimestamp("2026-09-22T12:00:00Z", now)).toBe(
      "Just now",
    );
    expect(formatRelativeTimestamp("2026-09-22T11:58:00Z", now)).toBe("2m ago");
    expect(formatRelativeTimestamp("2026-09-22T10:00:00Z", now)).toBe("2h ago");
    expect(formatRelativeTimestamp("2026-09-21T12:00:00Z", now)).toBe(
      "Yesterday",
    );
    expect(formatRelativeTimestamp("2026-09-19T12:00:00Z", now)).toBe("3d ago");
    expect(formatRelativeTimestamp("2026-08-01T12:00:00Z", now)).toBe(
      new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(
        new Date("2026-08-01T12:00:00Z"),
      ),
    );
    expect(formatRelativeTimestamp("2026-08-01T12:00:00Z", now)).toMatch(/^Aug 1, 2026, /);
  });
});
