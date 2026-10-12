/** Accepts API timestamps such as `2026-09-25 12:31:24.220271+05:30` in every browser. */
function parseTimestamp(value: string): Date {
  const normalized = value.trim().replace(" ", "T").replace(/(\.\d{3})\d+/, "$1");
  return new Date(normalized);
}

/** Absolute timestamps for titles/tooltips (UTC, stable for tests). */
export function formatAbsoluteTimestamp(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = parseTimestamp(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.toISOString().slice(0, 19).replace("T", " ")} UTC`;
}

const calendarFormatter = new Intl.DateTimeFormat("en", {
  dateStyle: "medium",
  timeStyle: "short",
});

/**
 * Human-friendly relative time. Pass `now` in tests for determinism.
 * Falls back to a calendar date when the delta is large, or the raw value when invalid.
 */
export function formatRelativeTimestamp(
  value: string | null | undefined,
  now: Date = new Date(),
): string | null {
  if (!value) return null;
  const then = parseTimestamp(value);
  if (Number.isNaN(then.getTime())) return value;

  const diffMs = then.getTime() - now.getTime();
  const absMs = Math.abs(diffMs);
  const past = diffMs <= 0;
  const seconds = Math.round(absMs / 1000);

  if (seconds < 45) return "Just now";

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return past ? `${minutes}m ago` : `in ${minutes}m`;
  }

  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return past ? `${hours}h ago` : `in ${hours}h`;
  }

  const days = Math.round(hours / 24);
  if (days === 1) return past ? "Yesterday" : "Tomorrow";
  if (days < 7) {
    return past ? `${days}d ago` : `in ${days}d`;
  }

  return calendarFormatter.format(then);
}
