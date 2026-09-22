/** Absolute timestamps for titles/tooltips (UTC, stable for tests). */
export function formatAbsoluteTimestamp(value: string | null | undefined): string | null {
  if (!value) return null;
  return value
    .replace("T", " ")
    .replace(/\.\d+Z$/, " UTC")
    .replace(/Z$/, " UTC");
}

/**
 * Human-friendly relative time. Pass `now` in tests for determinism.
 * Falls back to absolute when the delta is large or the value is invalid.
 */
export function formatRelativeTimestamp(
  value: string | null | undefined,
  now: Date = new Date(),
): string | null {
  if (!value) return null;
  const then = new Date(value);
  if (Number.isNaN(then.getTime())) return formatAbsoluteTimestamp(value);

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

  return formatAbsoluteTimestamp(value);
}
